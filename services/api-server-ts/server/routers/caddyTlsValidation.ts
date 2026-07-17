/**
 * caddyTlsValidation.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Caddy On-Demand TLS validation endpoint.
 *
 * When a TLS handshake arrives for an unknown hostname, Caddy calls:
 *   GET /internal/caddy/validate-domain?domain=<hostname>
 *
 * This handler queries the `tenant_branding.customDomain` column.
 * A 200 response authorises Caddy to provision a Let's Encrypt certificate
 * for that domain. A 403 response causes Caddy to reject the handshake.
 *
 * Security:
 *   - The endpoint is only called by Caddy from within the Docker/K8s network.
 *   - It is protected by the X-Internal-Key header (shared secret).
 *   - Rate limiting is applied at the Caddy level (burst: 5 per 2 minutes).
 *   - Domain input is validated against a strict regex before DB lookup.
 *
 * References:
 *   https://caddyserver.com/docs/automatic-https#on-demand-tls
 */

import { Router, Request, Response } from "express";
import { eq } from "drizzle-orm";
import { getDb } from "../db";
import { tenantBranding } from "../../drizzle/schema";
import { ENV } from "../_core/env";

// ── Domain validation regex ───────────────────────────────────────────────────
// Accepts valid FQDNs: labels of 1–63 chars, total length ≤ 253.
// Rejects IP addresses, localhost, and internal hostnames.
const FQDN_RE =
  /^(?!-)(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$/;

// Domains that must never be issued on-demand certs (platform-owned subdomains
// are handled by the main Caddyfile blocks, not the on-demand catch-all).
const BLOCKED_SUFFIXES = [
  "54link.ng",
  "54agent.io",
  "localhost",
  "local",
  "internal",
  "cluster.local",
];

function isBlockedDomain(domain: string): boolean {
  const lower = domain.toLowerCase();
  return BLOCKED_SUFFIXES.some(
    suffix => lower === suffix || lower.endsWith(`.${suffix}`)
  );
}

// ── Cache: avoid DB hit on every TLS handshake for the same domain ────────────
// TTL: 5 minutes. Entries are evicted on expiry or on explicit cache bust
// (triggered by the tenant onboarding webhook — see caddyWebhook.ts).
interface CacheEntry {
  allowed: boolean;
  expiresAt: number;
}
const domainCache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 5 * 60 * 1_000; // 5 minutes

function getCached(domain: string): boolean | null {
  const entry = domainCache.get(domain);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    domainCache.delete(domain);
    return null;
  }
  return entry.allowed;
}

function setCache(domain: string, allowed: boolean): void {
  domainCache.set(domain, {
    allowed,
    expiresAt: Date.now() + CACHE_TTL_MS,
  });
}

/** Evict a specific domain from the cache (call after tenant domain update). */
export function bustDomainCache(domain: string): void {
  domainCache.delete(domain);
}

/** Evict all entries (useful for testing). */
export function clearDomainCache(): void {
  domainCache.clear();
}

// ── Router ────────────────────────────────────────────────────────────────────
export const caddyTlsValidationRouter = Router();

/**
 * GET /internal/caddy/validate-domain?domain=<hostname>
 *
 * Called exclusively by Caddy's on_demand_tls `ask` mechanism.
 * Returns 200 if the domain is a registered, live tenant custom domain.
 * Returns 403 otherwise (Caddy will not issue a certificate).
 */
caddyTlsValidationRouter.get(
  "/internal/caddy/validate-domain",
  async (req: Request, res: Response) => {
    // ── 1. Internal-key authentication ────────────────────────────────────────
    // Caddy does not send auth headers by default, but we can configure it to
    // add a header via the Caddyfile `header_up` directive. When INTERNAL_API_KEY
    // is set, we enforce it; otherwise we rely on network-level isolation.
    const internalKey = ENV.internalApiKey;
    if (internalKey) {
      const provided = req.headers["x-internal-key"] as string | undefined;
      if (provided !== internalKey) {
        res.status(403).json({ error: "Forbidden" });
        return;
      }
    }

    // ── 2. Extract and validate the domain parameter ──────────────────────────
    const domain = (req.query.domain as string | undefined)?.trim().toLowerCase();

    if (!domain) {
      res.status(400).json({ error: "Missing domain parameter" });
      return;
    }

    if (!FQDN_RE.test(domain) || domain.length > 253) {
      res.status(403).json({ error: "Invalid domain format" });
      return;
    }

    if (isBlockedDomain(domain)) {
      // Platform-owned domains are handled by static Caddyfile blocks.
      // Issuing on-demand certs for them would be redundant and confusing.
      res.status(403).json({ error: "Domain is a platform-managed hostname" });
      return;
    }

    // ── 3. Cache lookup ───────────────────────────────────────────────────────
    const cached = getCached(domain);
    if (cached !== null) {
      if (cached) {
        res.status(200).json({ domain, allowed: true, source: "cache" });
      } else {
        res.status(403).json({ domain, allowed: false, source: "cache" });
      }
      return;
    }

    // ── 4. Database lookup ────────────────────────────────────────────────────
    try {
      const db = await getDb();
      const record = await db
        .select({ id: tenantBranding.id, isLive: tenantBranding.isLive })
        .from(tenantBranding)
        .where(eq(tenantBranding.customDomain, domain))
        .limit(1);

      const found = record.length > 0;
      // Only allow certs for tenants that have gone live (isLive = true).
      // This prevents cert issuance for tenants still in onboarding.
      const allowed = found && record[0].isLive === true;

      setCache(domain, allowed);

      if (allowed) {
        res.status(200).json({ domain, allowed: true, source: "db" });
      } else {
        res.status(403).json({
          domain,
          allowed: false,
          source: "db",
          reason: found ? "tenant_not_live" : "domain_not_registered",
        });
      }
    } catch (err) {
      // On DB error, deny the cert to fail safe.
      console.error("[Caddy TLS] DB lookup failed for domain:", domain, err);
      res.status(500).json({ error: "Internal error — cert issuance denied" });
    }
  }
);

/**
 * POST /internal/caddy/bust-cache
 *
 * Called by the tenant onboarding flow after a custom domain is registered
 * or updated, so the next Caddy handshake re-queries the DB.
 * Protected by X-Internal-Key header.
 */
caddyTlsValidationRouter.post(
  "/internal/caddy/bust-cache",
  (req: Request, res: Response) => {
    const internalKey = ENV.internalApiKey;
    if (internalKey) {
      const provided = req.headers["x-internal-key"] as string | undefined;
      if (provided !== internalKey) {
        res.status(403).json({ error: "Forbidden" });
        return;
      }
    }

    const { domain } = req.body as { domain?: string };
    if (!domain) {
      res.status(400).json({ error: "Missing domain in request body" });
      return;
    }

    bustDomainCache(domain.trim().toLowerCase());
    res.status(200).json({ message: `Cache cleared for ${domain}` });
  }
);
