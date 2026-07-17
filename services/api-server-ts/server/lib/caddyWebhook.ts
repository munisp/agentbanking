/**
 * caddyWebhook.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Caddy Admin API client for the tenant onboarding flow.
 *
 * When a tenant registers or updates a custom domain, this module:
 *   1. Busts the on-demand TLS validation cache for the old/new domain.
 *   2. (Optional) Calls the Caddy Admin API to pre-warm the certificate
 *      by triggering a TLS handshake probe — this avoids the first-visitor
 *      latency of on-demand cert provisioning.
 *
 * The Caddy Admin API is bound to localhost:2019 inside the container and
 * exposed at caddy-admin.<DOMAIN> (internal only) via the Caddyfile.
 *
 * References:
 *   https://caddyserver.com/docs/api
 */

import { ENV } from "../_core/env";

const CADDY_ADMIN_URL = process.env.CADDY_ADMIN_URL ?? "http://caddy:2019";

/**
 * Notify Caddy that a tenant custom domain has been registered or updated.
 * This triggers cache invalidation and optionally pre-warms the TLS cert.
 */
export async function notifyCaddyDomainRegistered(
  domain: string,
  options: { prewarm?: boolean } = {}
): Promise<void> {
  const normalised = domain.trim().toLowerCase();

  // Step 1: Bust the local validation cache via the internal endpoint.
  // This ensures the next on-demand TLS check re-queries the DB.
  try {
    const bustUrl = `${process.env.APP_INTERNAL_URL ?? "http://localhost:3000"}/internal/caddy/bust-cache`;
    await fetch(bustUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(ENV.internalApiKey
          ? { "X-Internal-Key": ENV.internalApiKey }
          : {}),
      },
      body: JSON.stringify({ domain: normalised }),
      signal: AbortSignal.timeout(5_000),
    });
  } catch (err) {
    // Non-fatal — cache will expire naturally after 5 minutes
    console.warn("[Caddy] Cache bust failed (non-fatal):", err);
  }

  // Step 2: (Optional) Pre-warm the certificate via Caddy Admin API.
  // POST /certificates/automate  triggers Caddy to begin ACME for the domain.
  if (options.prewarm) {
    try {
      const resp = await fetch(`${CADDY_ADMIN_URL}/certificates/automate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([normalised]),
        signal: AbortSignal.timeout(10_000),
      });
      if (!resp.ok) {
        const body = await resp.text();
        console.warn(
          `[Caddy] Pre-warm request failed (${resp.status}): ${body}`
        );
      } else {
        console.info(`[Caddy] Pre-warm triggered for domain: ${normalised}`);
      }
    } catch (err) {
      // Non-fatal — on-demand TLS will provision the cert on first request
      console.warn("[Caddy] Pre-warm request failed (non-fatal):", err);
    }
  }
}

/**
 * Remove a domain from Caddy's certificate automation when a tenant
 * deactivates or changes their custom domain.
 */
export async function notifyCaddyDomainRemoved(domain: string): Promise<void> {
  const normalised = domain.trim().toLowerCase();
  const encodedDomain = encodeURIComponent(normalised);

  try {
    const resp = await fetch(
      `${CADDY_ADMIN_URL}/certificates/automate/${encodedDomain}`,
      {
        method: "DELETE",
        signal: AbortSignal.timeout(10_000),
      }
    );
    if (!resp.ok && resp.status !== 404) {
      const body = await resp.text();
      console.warn(
        `[Caddy] Domain removal failed (${resp.status}): ${body}`
      );
    } else {
      console.info(`[Caddy] Domain removed from automation: ${normalised}`);
    }
  } catch (err) {
    console.warn("[Caddy] Domain removal request failed (non-fatal):", err);
  }
}

/**
 * Query the Caddy Admin API for the current certificate status of a domain.
 * Useful for the admin dashboard to show cert provisioning progress.
 */
export async function getCaddyCertStatus(domain: string): Promise<{
  managed: boolean;
  notBefore?: string;
  notAfter?: string;
  issuer?: string;
} | null> {
  const normalised = domain.trim().toLowerCase();
  const encodedDomain = encodeURIComponent(normalised);

  try {
    const resp = await fetch(
      `${CADDY_ADMIN_URL}/pki/ca/local/certificates/${encodedDomain}`,
      { signal: AbortSignal.timeout(5_000) }
    );
    if (!resp.ok) return null;
    const data = (await resp.json()) as Record<string, unknown>;
    return {
      managed: true,
      notBefore: data.not_before as string | undefined,
      notAfter: data.not_after as string | undefined,
      issuer: data.issuer as string | undefined,
    };
  } catch {
    return null;
  }
}
