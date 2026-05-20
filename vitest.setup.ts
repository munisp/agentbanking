/**
 * Global test setup — mocks external service calls that fail due to DNS/network
 * issues in CI. Only intercepts calls to hosts that are never available in test.
 */

// ── Mock fetch for external-only hosts (not localhost) ────────────────────────
const originalFetch = globalThis.fetch;

globalThis.fetch = async (
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> => {
  const url = typeof input === "string" ? input : input.toString();

  // Only intercept calls to external hosts that will DNS-fail in CI
  const isLocalhost = url.includes("localhost") || url.includes("127.0.0.1");
  if (
    !isLocalhost &&
    (url.includes("tigerbeetle-sidecar") ||
      url.includes("permify") ||
      url.includes("apisix") ||
      url.includes("keycloak") ||
      url.includes("kafka"))
  ) {
    return new Response(JSON.stringify({ ok: true, data: [], allowed: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Everything else (including localhost sidecars) goes through normally
  return originalFetch(input, init);
};

// ── Suppress noisy console output from expected test-environment failures ──────
const originalError = console.error;
const originalWarn = console.warn;

const SUPPRESS_PATTERNS = [
  "EAI_AGAIN",
  "ECONNREFUSED",
  "fetch failed",
  "ENOTFOUND",
  "ETIMEDOUT",
];

console.error = (...args: unknown[]) => {
  const msg = String(args[0] ?? "");
  if (SUPPRESS_PATTERNS.some(p => msg.includes(p))) return;
  originalError.apply(console, args);
};

console.warn = (...args: unknown[]) => {
  const msg = String(args[0] ?? "");
  if (SUPPRESS_PATTERNS.some(p => msg.includes(p))) return;
  originalWarn.apply(console, args);
};
