/**
 * Vitest Global Setup
 * ==================
 * Mocks all external service HTTP calls so tests can run without
 * Docker services (Keycloak, TigerBeetle, PostgreSQL, Redis, etc.)
 */
import { vi, beforeAll, afterAll } from "vitest";

// ── Environment variables for tests ──────────────────────────────────────────
process.env.NODE_ENV = "test";
process.env.DATABASE_URL = "postgresql://test:test@localhost:5432/testdb";
process.env.REDIS_URL = "redis://localhost:6379";
process.env.KEYCLOAK_URL = "http://localhost:8080";
process.env.KEYCLOAK_REALM = "agentbanking";
process.env.KEYCLOAK_CLIENT_ID = "api-server";
process.env.KEYCLOAK_CLIENT_SECRET = "test-secret";
process.env.TIGERBEETLE_ADDRESS = "localhost:3000";
process.env.TEMPORAL_ADDRESS = "localhost:7233";
process.env.PERMIFY_URL = "http://localhost:3478";
process.env.DAPR_HTTP_PORT = "3500";
process.env.DAPR_GRPC_PORT = "50001";
process.env.FLUVIO_GATEWAY_URL = "http://localhost:9090";
process.env.OPENAI_API_BASE = "http://localhost:11434/v1";
process.env.OPENAI_API_KEY = "test-openai-key";
process.env.DATA_API_BASE_URL = "http://localhost:3001/api";
process.env.DATA_API_KEY = "test-data-key";
process.env.HEARTBEAT_API_URL = "http://localhost:3001/health";
process.env.HEARTBEAT_API_KEY = "test-heartbeat-key";
process.env.MAPS_API_BASE_URL = "http://localhost:3001/maps";
process.env.GOOGLE_MAPS_API_KEY = "test-maps-key";
process.env.JWT_SECRET = "test-jwt-secret-at-least-32-characters-long";
process.env.S3_ENDPOINT = "http://localhost:9000";
process.env.S3_ACCESS_KEY = "minioadmin";
process.env.S3_SECRET_KEY = "minioadmin";
process.env.S3_BUCKET = "agentbanking";
process.env.SMTP_HOST = "localhost";
process.env.SMTP_PORT = "1025";
process.env.SMTP_USER = "test@test.local";
process.env.SMTP_PASS = "test";

// ── Mock global fetch ─────────────────────────────────────────────────────────
const mockFetch = vi.fn(async (url: string | URL | Request, _init?: RequestInit) => {
  const urlStr = url instanceof Request ? url.url : url.toString();

  // Keycloak token endpoint
  if (urlStr.includes("keycloak") || urlStr.includes(":8080")) {
    return new Response(
      JSON.stringify({
        access_token: "mock-access-token",
        token_type: "Bearer",
        expires_in: 3600,
        refresh_token: "mock-refresh-token",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Permify check endpoint
  if (urlStr.includes("permify") || urlStr.includes(":3478")) {
    return new Response(
      JSON.stringify({ can: "RESULT_ALLOWED" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Dapr sidecar
  if (urlStr.includes(":3500") || urlStr.includes("dapr")) {
    return new Response(
      JSON.stringify({ status: "ok" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Fluvio gateway
  if (urlStr.includes(":9090") || urlStr.includes("fluvio")) {
    return new Response(
      JSON.stringify({ offset: 1, partition: 0 }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Temporal
  if (urlStr.includes(":7233") || urlStr.includes("temporal")) {
    return new Response(
      JSON.stringify({ workflowId: "mock-workflow-id", runId: "mock-run-id" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // OpenAI / LLM
  if (urlStr.includes("openai") || urlStr.includes(":11434")) {
    return new Response(
      JSON.stringify({
        id: "mock-completion",
        choices: [{ message: { role: "assistant", content: "Mock response" }, finish_reason: "stop" }],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // Data API / Heartbeat / Maps
  if (urlStr.includes("localhost:3001")) {
    return new Response(
      JSON.stringify({ status: "ok", data: [] }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  // MinIO / S3
  if (urlStr.includes(":9000") || urlStr.includes("minio")) {
    return new Response("", { status: 200 });
  }

  // Default: return 200 OK
  return new Response(
    JSON.stringify({ status: "ok" }),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );
});

// ── Mock SignJWT and jwtVerify from jose ──────────────────────────────────────
vi.mock("jose", async () => {
  const actual = await vi.importActual<typeof import("jose")>("jose");
  return {
    ...actual,
    SignJWT: class MockSignJWT {
      private payload: Record<string, unknown> = {};
      constructor(payload: Record<string, unknown>) {
        this.payload = payload;
      }
      setProtectedHeader(_header: unknown) { return this; }
      setIssuedAt() { return this; }
      setExpirationTime(_exp: unknown) { return this; }
      setSubject(_sub: string) { return this; }
      setIssuer(_iss: string) { return this; }
      setAudience(_aud: unknown) { return this; }
      async sign(_key: unknown) {
        return "mock.jwt.token." + Buffer.from(JSON.stringify(this.payload)).toString("base64url");
      }
    },
    jwtVerify: vi.fn(async (token: string) => {
      const parts = token.split(".");
      const payload = parts[3]
        ? JSON.parse(Buffer.from(parts[3], "base64url").toString())
        : { sub: "mock-user-id", role: "agent" };
      return { payload, protectedHeader: { alg: "HS256" } };
    }),
    createRemoteJWKSet: vi.fn(() => async () => ({ type: "mock-jwks" })),
    importSPKI: vi.fn(async () => ({ type: "mock-key" })),
    importPKCS8: vi.fn(async () => ({ type: "mock-key" })),
    generateKeyPair: vi.fn(async () => ({
      publicKey: { type: "mock-public-key" },
      privateKey: { type: "mock-private-key" },
    })),
  };
});

// ── Mock drizzle-orm database connection ──────────────────────────────────────
vi.mock("./server/_core/db", () => ({
  db: {
    select: vi.fn(() => ({ from: vi.fn(() => ({ where: vi.fn(() => Promise.resolve([])) })) })),
    insert: vi.fn(() => ({ values: vi.fn(() => ({ returning: vi.fn(() => Promise.resolve([{ id: "mock-id" }])) })) })),
    update: vi.fn(() => ({ set: vi.fn(() => ({ where: vi.fn(() => ({ returning: vi.fn(() => Promise.resolve([{ id: "mock-id" }])) })) })) })),
    delete: vi.fn(() => ({ where: vi.fn(() => Promise.resolve([])) })),
    transaction: vi.fn(async (fn: (tx: unknown) => Promise<unknown>) => fn({})),
    query: {},
  },
}));

// ── Apply fetch mock globally ─────────────────────────────────────────────────
beforeAll(() => {
  global.fetch = mockFetch as typeof fetch;
});

afterAll(() => {
  vi.restoreAllMocks();
});
