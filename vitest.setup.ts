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

  // Intercept calls to external hosts that will DNS-fail in CI
  const isLocalhost = url.includes("localhost") || url.includes("127.0.0.1");
  const isExternalSidecar =
    !isLocalhost &&
    (url.includes("tigerbeetle-sidecar") ||
      url.includes("permify") ||
      url.includes("apisix") ||
      url.includes("keycloak") ||
      url.includes("kafka"));

  // Local sidecars that are never running in the test/CI environment. These are
  // hit by fire-and-forget financial fan-out (Fluvio :9090, Lakehouse :8156,
  // MinIO :9000); left un-intercepted they fail late and log during vitest
  // worker teardown, causing "Closing rpc while onUserConsoleLog was pending".
  const isLocalSidecar =
    isLocalhost &&
    (url.includes(":9090") || url.includes(":8156") || url.includes(":9000"));

  if (isExternalSidecar || isLocalSidecar) {
    return new Response(JSON.stringify({ ok: true, data: [], allowed: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Everything else (including the app's own localhost server) goes through normally
  return originalFetch(input, init);
};

// ── Suppress noisy console output from expected test-environment failures ──────
// Background clients (Kafka, Redis, sidecars) attempt connections that fail in
// CI/test. Their error handlers fire asynchronously — often after a test file
// has finished — and any console call at that point is forwarded to vitest's
// worker RPC, which is already closing, producing:
//   EnvironmentTeardownError: Closing rpc while "onUserConsoleLog" was pending
// Dropping these benign logs (before they reach vitest's patched console)
// eliminates that flaky teardown race. We check ALL args, not just the first,
// because messages like `[Redis] Connection error:` carry the cause in args[1].
const originalError = console.error;
const originalWarn = console.warn;
const originalLog = console.log;
const originalInfo = console.info;

const SUPPRESS_PATTERNS = [
  "EAI_AGAIN",
  "ECONNREFUSED",
  "fetch failed",
  "ENOTFOUND",
  "ETIMEDOUT",
  "kafkajs",
  "[Kafka]",
  "[Redis]",
  "[Fluvio]",
  "[Lakehouse]",
  "Connection error",
  "getaddrinfo",
];

const shouldSuppress = (args: unknown[]): boolean => {
  const msg = args.map(a => String(a ?? "")).join(" ");
  return SUPPRESS_PATTERNS.some(p => msg.includes(p));
};

console.error = (...args: unknown[]) => {
  if (shouldSuppress(args)) return;
  originalError.apply(console, args);
};

console.warn = (...args: unknown[]) => {
  if (shouldSuppress(args)) return;
  originalWarn.apply(console, args);
};

console.log = (...args: unknown[]) => {
  if (shouldSuppress(args)) return;
  originalLog.apply(console, args);
};

console.info = (...args: unknown[]) => {
  if (shouldSuppress(args)) return;
  originalInfo.apply(console, args);
};
