/**
 * Global test setup — mocks external service calls that fail due to DNS/network
 * issues in CI. Only intercepts calls to hosts that are never available in test.
 */

// ── Mock fetch for external-only hosts (not localhost) ────────────────────────
const originalFetch = globalThis.fetch;

// Ports that belong to Docker-only services (Fluvio, Dapr, TigerBeetle, Lakehouse, APISIX, Temporal, sidecars)
const DOCKER_ONLY_PORTS = [
  ":9090",  // Fluvio HTTP gateway
  ":3500",  // Dapr sidecar HTTP
  ":7480",  // TigerBeetle sidecar
  ":8888",  // Lakehouse / Delta Sharing
  ":9080",  // APISIX admin
  ":7233",  // Temporal frontend
  ":2379",  // etcd
  ":9100",  // Rust middleware bridge
  ":9200",  // Go ledger sync
  ":9300",  // Python ML service
  ":3476",  // Permify authorization
  ":8156",  // Lakehouse unified API
  ":8080",  // Generic sidecar HTTP
  ":9092",  // Kafka broker
  ":8443",  // Keycloak HTTPS
  ":8180",  // Keycloak HTTP
];

// External hostnames that are only available in Docker / production
const DOCKER_ONLY_HOSTS = [
  "tigerbeetle-sidecar",
  "permify",
  "apisix",
  "keycloak",
  "kafka",
  "fluvio",
  "temporal",
  "dapr",
  "lakehouse",
  "minio",
  "opensearch",
  "trino",
  "spark",
];

globalThis.fetch = async (
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> => {
  const url = typeof input === "string" ? input : input.toString();
  const isLocalhost = url.includes("localhost") || url.includes("127.0.0.1");

  // Intercept external Docker service hostnames (DNS will fail in CI)
  if (!isLocalhost && DOCKER_ONLY_HOSTS.some(h => url.includes(h))) {
    // TigerBeetle sidecar must return a non-OK status so fail-closed middleware throws.
    // tbCreateTransfer checks `if (!res.ok)` and returns null, which triggers the throw.
    if (url.includes("tigerbeetle-sidecar")) {
      return new Response(
        JSON.stringify({ error: "Service unavailable (test mock)" }),
        { status: 503, headers: { "Content-Type": "application/json" } }
      );
    }
    // Permify in Docker — return correct shape
    if (url.includes("permify") && url.includes("/permissions/check")) {
      return new Response(
        JSON.stringify({ can: "CHECK_RESULT_ALLOWED", metadata: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    // All other Docker-only hostnames
    return new Response(
      JSON.stringify({ ok: true, data: [], allowed: true, id: "mock-id", status: "committed" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Intercept localhost ports that belong to Docker-only services
  if (isLocalhost && DOCKER_ONLY_PORTS.some(p => url.includes(p))) {
    // ── Permify authorization service (port 3476) ────────────────────────────
    // Must return the exact Permify JSON shape so permifyCheck() returns true (fail-open).
    if (url.includes(":3476") && url.includes("/permissions/check")) {
      return new Response(
        JSON.stringify({ can: "CHECK_RESULT_ALLOWED", metadata: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    if (url.includes(":3476") && url.includes("/relationships/write")) {
      return new Response(
        JSON.stringify({ snap_token: { token: "mock-snap-token" } }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }
    if (url.includes(":3476")) {
      return new Response(
        JSON.stringify({ can: "CHECK_RESULT_ALLOWED" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // ── Sidecar services (Rust :9100, Go :9200, Python :9300) ───────────────
    // These services use a try/catch with explicit fallback values in sidecarBridge.ts.
    // Returning a network error (rejected promise) triggers the catch block and the
    // correct typed fallback is returned. A 500 response would be parsed as JSON and
    // override the fallback, so we must simulate a connection refusal instead.
    if (url.includes(":9100") || url.includes(":9200") || url.includes(":9300")) {
      throw new TypeError("fetch failed: ECONNREFUSED (test mock)");
    }

    // ── Dapr state store GET — must return 404 (no cached state) so procedures
    // fall through to their actual calculation/DB logic instead of returning
    // the mock object as a cached result.
    if (url.includes(":3500") && url.includes("/v1.0/state/") && (!init || init.method === undefined || init.method === "GET")) {
      return new Response("", { status: 404 });
    }

    // ── All other Docker-only service ports ─────────────────────────────────
    return new Response(
      JSON.stringify({ ok: true, data: [], allowed: true, id: "mock-id", status: "committed" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Everything else (including localhost:5432 DB, localhost:6379 Redis) goes through normally
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
  "Connection error",
  "AggregateError",
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
