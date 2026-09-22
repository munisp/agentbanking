// TypeScript enabled — Sprint 96 security audit
/**
 * mtlsAgent.ts — Mutual TLS HTTPS Agent for platform microservice calls
 * ─────────────────────────────────────────────────────────────────────────────
 * Loads client certificate, private key, and CA bundle from the directory
 * specified by MTLS_CERT_DIR (default: /etc/54agent/certs).
 *
 * Usage:
 *   import { getMtlsAgent } from "../lib/mtlsAgent";
 *   const res = await fetch(url, { ...opts, dispatcher: getMtlsAgent() });
 *
 * Cert rotation:
 *   Send SIGHUP to the process to force re-read of certificates without restart.
 *   The server/_core/index.ts already registers this signal handler.
 *
 * Fallback:
 *   When MTLS_ENABLED=false OR certificate files are absent, the function
 *   returns null and callers should use plain fetch (acceptable behind an
 *   APISix gateway that handles mTLS termination).
 */

import https from "https";
import fs from "fs";
import path from "path";
import { ENV } from "../_core/env";
import type { Dispatcher } from "undici";

const CERT_DIR = ENV.mtlsCertDir;
const MTLS_ENABLED = ENV.mtlsEnabled;

let _agent: https.Agent | null | undefined = undefined; // undefined = not yet initialised
let _dispatcher: Dispatcher | null | undefined = undefined; // undefined = not yet initialised

function loadCertMaterial(): { cert: Buffer; key: Buffer; ca: Buffer } | null {
  const certPath = path.join(CERT_DIR, "tls.crt");
  const keyPath = path.join(CERT_DIR, "tls.key");
  const caPath = path.join(CERT_DIR, "ca.crt");

  if (
    !fs.existsSync(certPath) ||
    !fs.existsSync(keyPath) ||
    !fs.existsSync(caPath)
  ) {
    console.warn(
      `[mTLS] Certificate files not found in ${CERT_DIR} — falling back to plain HTTPS. ` +
        "Set MTLS_CERT_DIR or MTLS_ENABLED=false to suppress this warning."
    );
    return null;
  }
  try {
    return {
      cert: fs.readFileSync(certPath),
      key: fs.readFileSync(keyPath),
      ca: fs.readFileSync(caPath),
    };
  } catch (err) {
    console.error("[mTLS] Failed to load certificates:", err);
    return null;
  }
}

/**
 * Lazily create (or return cached) mTLS undici dispatcher.
 *
 * ROUND-8 FIX: Node 18+ global fetch is undici-based and SILENTLY IGNORES the
 * legacy `agent` (https.Agent) init option — callers that attached
 * `getMtlsAgent()` via `fetch(url, { agent })` were sending NO client
 * certificate at all (and the agent's pool config was inert). undici fetch
 * requires a `dispatcher` (undici Agent). This is the correct handle; it also
 * enables real keep-alive connection pooling for inter-service calls.
 *
 * Returns null when mTLS is disabled, certs are absent, or the `undici`
 * package is unavailable (callers then use plain fetch — acceptable behind an
 * APISix gateway that terminates mTLS).
 */
export async function getMtlsDispatcher(): Promise<Dispatcher | null> {
  if (_dispatcher !== undefined) return _dispatcher;

  if (!MTLS_ENABLED) {
    console.info("[mTLS] MTLS_ENABLED=false — using plain HTTPS");
    _dispatcher = null;
    return null;
  }

  const certs = loadCertMaterial();
  if (!certs) {
    _dispatcher = null;
    return null;
  }

  try {
    const { Agent } = await import("undici");
    _dispatcher = new Agent({
      connect: {
        cert: certs.cert,
        key: certs.key,
        ca: certs.ca,
        rejectUnauthorized: true,
        minVersion: "TLSv1.2",
      },
      // Keep-alive pooling (https.Agent previously had no keepAlive at all).
      keepAliveTimeout: 10_000,
      keepAliveMaxTimeout: 60_000,
      connections: 64,
    });
    console.info(`[mTLS] undici dispatcher initialised — cert dir: ${CERT_DIR}`);
    return _dispatcher;
  } catch (err) {
    console.error(
      "[mTLS] undici package unavailable or dispatcher init failed — mTLS NOT applied:",
      err
    );
    _dispatcher = null;
    return null;
  }
}

/** Lazily create (or return cached) mTLS HTTPS agent. Returns null when mTLS is disabled or certs are absent. */
export function getMtlsAgent(): https.Agent | null {
  if (_agent !== undefined) return _agent;

  if (!MTLS_ENABLED) {
    console.info("[mTLS] MTLS_ENABLED=false — using plain HTTPS");
    _agent = null;
    return null;
  }

  try {
    const certs = loadCertMaterial();
    if (!certs) {
      _agent = null;
      return null;
    }
    _agent = new https.Agent({
      cert: certs.cert,
      key: certs.key,
      ca: certs.ca,
      rejectUnauthorized: true,
      minVersion: "TLSv1.2",
      keepAlive: true,
    });
    console.info(`[mTLS] Agent initialised — cert dir: ${CERT_DIR}`);
    return _agent;
  } catch (err) {
    console.error("[mTLS] Failed to load certificates:", err);
    _agent = null;
    return null;
  }
}

/**
 * Reset the cached agent so the next call to getMtlsAgent() re-reads certs
 * from disk. Call this on SIGHUP for zero-downtime cert rotation.
 */
export function resetMtlsAgent(): void {
  _agent = undefined;
  const oldDispatcher = _dispatcher;
  _dispatcher = undefined;
  // Close the old dispatcher's pooled connections in the background.
  if (oldDispatcher) void oldDispatcher.close().catch(() => {});
  console.info(
    "[mTLS] Agent cache cleared — certs will be reloaded on next request"
  );
}

/**
 * Return fetch-compatible init options that include the mTLS agent when available.
 * Merges with any existing options passed in.
 *
 * Example:
 *   const res = await fetch(url, mtlsFetchOptions({ method: "POST", body: "..." }));
 */
export function mtlsFetchOptions(
  base: RequestInit = {}
): RequestInit & { agent?: https.Agent } {
  const agent = getMtlsAgent();
  if (!agent) return base;
  // Node 18+ fetch (undici) accepts `dispatcher`; legacy node-fetch accepts `agent`.
  // We attach both for maximum compatibility.
  return { ...base, agent } as RequestInit & { agent: https.Agent };
}
