/**
 * Caddy On-Demand TLS Validation — Unit Tests
 * ============================================
 * Tests the /internal/caddy/validate-domain and /internal/caddy/bust-cache
 * endpoints that gate Caddy's on-demand TLS certificate issuance for
 * white-label tenant custom domains.
 *
 * All DB calls are mocked via vi.mock so no real database is needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";

// ── Mocks ─────────────────────────────────────────────────────────────────────
// The router imports from "../db" and "../_core/env" (relative to routers/).
// We must mock the resolved module paths as vitest sees them.

vi.mock("../server/db", () => ({
  getDb: vi.fn(),
}));

vi.mock("../server/_core/env", () => ({
  ENV: {
    internalApiKey: "",
  },
}));

// ── Imports (after mocks are set up) ─────────────────────────────────────────
import { getDb } from "../server/db";
import { ENV } from "../server/_core/env";
import {
  caddyTlsValidationRouter,
  clearDomainCache,
} from "../server/routers/caddyTlsValidation";

// ── Test app setup ────────────────────────────────────────────────────────────
function buildApp() {
  const app = express();
  app.use(express.json());
  app.use(caddyTlsValidationRouter);
  return app;
}

// ── DB mock helpers ───────────────────────────────────────────────────────────
function mockDbWithDomain(isLive: boolean) {
  const mockLimit = vi.fn().mockResolvedValue([{ id: "tenant-1", isLive }]);
  const mockWhere = vi.fn().mockReturnValue({ limit: mockLimit });
  const mockFrom = vi.fn().mockReturnValue({ where: mockWhere });
  const mockSelect = vi.fn().mockReturnValue({ from: mockFrom });
  (getDb as ReturnType<typeof vi.fn>).mockResolvedValue({ select: mockSelect });
}

function mockDbWithNoDomain() {
  const mockLimit = vi.fn().mockResolvedValue([]);
  const mockWhere = vi.fn().mockReturnValue({ limit: mockLimit });
  const mockFrom = vi.fn().mockReturnValue({ where: mockWhere });
  const mockSelect = vi.fn().mockReturnValue({ from: mockFrom });
  (getDb as ReturnType<typeof vi.fn>).mockResolvedValue({ select: mockSelect });
}

function mockDbError() {
  const mockLimit = vi.fn().mockRejectedValue(new Error("DB connection failed"));
  const mockWhere = vi.fn().mockReturnValue({ limit: mockLimit });
  const mockFrom = vi.fn().mockReturnValue({ where: mockWhere });
  const mockSelect = vi.fn().mockReturnValue({ from: mockFrom });
  (getDb as ReturnType<typeof vi.fn>).mockResolvedValue({ select: mockSelect });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("GET /internal/caddy/validate-domain", () => {
  let app: ReturnType<typeof buildApp>;

  beforeEach(() => {
    app = buildApp();
    clearDomainCache();
    // Reset ENV: empty string means "no key required"
    (ENV as { internalApiKey: string }).internalApiKey = "";
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearDomainCache();
  });

  // ── Happy path ──────────────────────────────────────────────────────────────

  it("returns 200 for a registered, live tenant custom domain", async () => {
    mockDbWithDomain(true);
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });
    expect(res.status).toBe(200);
    expect(res.body.allowed).toBe(true);
    expect(res.body.source).toBe("db");
  });

  it("returns 200 from cache on second request (no second DB call)", async () => {
    mockDbWithDomain(true);
    // First request — hits DB
    await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });
    // Second request — should hit cache
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });
    expect(res.status).toBe(200);
    expect(res.body.source).toBe("cache");
    // DB should only have been called once
    expect(getDb).toHaveBeenCalledTimes(1);
  });

  it("normalises domain to lowercase before lookup", async () => {
    mockDbWithDomain(true);
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "APP.THEIRBANK.COM" });
    expect(res.status).toBe(200);
  });

  // ── Denial cases ────────────────────────────────────────────────────────────

  it("returns 403 for a registered but not-yet-live tenant domain", async () => {
    mockDbWithDomain(false);
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "staging.theirbank.com" });
    expect(res.status).toBe(403);
    expect(res.body.reason).toBe("tenant_not_live");
  });

  it("returns 403 for an unregistered domain", async () => {
    mockDbWithNoDomain();
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "unknown.example.com" });
    expect(res.status).toBe(403);
    expect(res.body.reason).toBe("domain_not_registered");
  });

  it("returns 403 for a platform-owned domain (54link.ng)", async () => {
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "54link.ng" });
    expect(res.status).toBe(403);
    expect(res.body.error).toMatch(/platform-managed/i);
  });

  it("returns 403 for a platform subdomain (api.54link.ng)", async () => {
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "api.54link.ng" });
    expect(res.status).toBe(403);
  });

  it("returns 403 for a localhost domain", async () => {
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "localhost" });
    expect(res.status).toBe(403);
  });

  it("returns 400 when the domain query parameter is missing", async () => {
    const res = await request(app).get("/internal/caddy/validate-domain");
    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/missing domain/i);
  });

  it("returns 403 for an invalid domain format (IP address)", async () => {
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "192.168.1.1" });
    expect(res.status).toBe(403);
  });

  it("returns 403 for an excessively long domain (>253 chars)", async () => {
    const longDomain =
      "a".repeat(64) + "." + "b".repeat(64) + "." + "c".repeat(64) + ".com";
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: longDomain });
    expect(res.status).toBe(403);
  });

  // ── Authentication ──────────────────────────────────────────────────────────

  it("returns 403 when INTERNAL_API_KEY is set and key is missing", async () => {
    (ENV as { internalApiKey: string }).internalApiKey = "secret-key";
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });
    expect(res.status).toBe(403);
  });

  it("returns 403 when INTERNAL_API_KEY is set and key is wrong", async () => {
    (ENV as { internalApiKey: string }).internalApiKey = "secret-key";
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .set("x-internal-key", "wrong-key")
      .query({ domain: "app.theirbank.com" });
    expect(res.status).toBe(403);
  });

  it("returns 200 when INTERNAL_API_KEY is set and correct key is provided", async () => {
    (ENV as { internalApiKey: string }).internalApiKey = "secret-key";
    mockDbWithDomain(true);
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .set("x-internal-key", "secret-key")
      .query({ domain: "app.theirbank.com" });
    expect(res.status).toBe(200);
  });

  // ── Error handling ──────────────────────────────────────────────────────────

  it("returns 500 and denies cert when DB throws an error", async () => {
    mockDbError();
    const res = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });
    expect(res.status).toBe(500);
    expect(res.body.error).toMatch(/internal error/i);
  });
});

// ── Cache bust endpoint ───────────────────────────────────────────────────────

describe("POST /internal/caddy/bust-cache", () => {
  let app: ReturnType<typeof buildApp>;

  beforeEach(() => {
    app = buildApp();
    clearDomainCache();
    (ENV as { internalApiKey: string }).internalApiKey = "";
    vi.clearAllMocks();
  });

  afterEach(() => {
    clearDomainCache();
  });

  it("clears the cache for a given domain and returns 200", async () => {
    // Populate cache with a denied entry
    mockDbWithNoDomain();
    await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });

    // Now the domain is in cache as denied. Bust it.
    const bustRes = await request(app)
      .post("/internal/caddy/bust-cache")
      .send({ domain: "app.theirbank.com" });
    expect(bustRes.status).toBe(200);

    // Next validate call should hit DB again (cache was cleared)
    mockDbWithDomain(true);
    const validateRes = await request(app)
      .get("/internal/caddy/validate-domain")
      .query({ domain: "app.theirbank.com" });
    expect(validateRes.status).toBe(200);
    expect(validateRes.body.source).toBe("db");
    // DB was called twice total (once before bust, once after)
    expect(getDb).toHaveBeenCalledTimes(2);
  });

  it("returns 400 when domain is missing from body", async () => {
    const res = await request(app)
      .post("/internal/caddy/bust-cache")
      .send({});
    expect(res.status).toBe(400);
  });

  it("returns 403 when INTERNAL_API_KEY is set and key is wrong", async () => {
    (ENV as { internalApiKey: string }).internalApiKey = "secret-key";
    const res = await request(app)
      .post("/internal/caddy/bust-cache")
      .set("x-internal-key", "wrong-key")
      .send({ domain: "app.theirbank.com" });
    expect(res.status).toBe(403);
  });

  it("returns 200 when INTERNAL_API_KEY is set and correct key is provided", async () => {
    (ENV as { internalApiKey: string }).internalApiKey = "secret-key";
    const res = await request(app)
      .post("/internal/caddy/bust-cache")
      .set("x-internal-key", "secret-key")
      .send({ domain: "app.theirbank.com" });
    expect(res.status).toBe(200);
  });
});
