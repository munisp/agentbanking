/**
 * Integration Test: Admin Dashboard & System Management
 * Tests admin procedures, system stats, user management, and platform health.
 *
 * Run: pnpm test tests/integration/admin-dashboard.test.ts
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { appRouter } from "../../server/routers";
import type { TrpcContext } from "../../server/_core/context";

vi.mock("../../server/db", () => ({
  getDb: vi.fn().mockResolvedValue({
    select: vi.fn().mockReturnValue({
      from: vi.fn().mockReturnValue({
        where: vi.fn().mockReturnValue({
          orderBy: vi.fn().mockReturnValue({
            limit: vi.fn().mockReturnValue({
              offset: vi.fn().mockResolvedValue([]),
            }),
          }),
          limit: vi.fn().mockResolvedValue([{ cnt: 5 }]),
        }),
        orderBy: vi.fn().mockReturnValue({
          limit: vi.fn().mockReturnValue({
            offset: vi.fn().mockResolvedValue([]),
          }),
        }),
        limit: vi.fn().mockResolvedValue([{ cnt: 10, t: "1000" }]),
      }),
    }),
    insert: vi.fn().mockReturnValue({
      values: vi.fn().mockReturnValue({
        returning: vi.fn().mockResolvedValue([{ id: 1 }]),
        onConflictDoNothing: vi.fn().mockResolvedValue(undefined),
      }),
    }),
    update: vi.fn().mockReturnValue({
      set: vi.fn().mockReturnValue({
        where: vi.fn().mockReturnValue({
          returning: vi.fn().mockResolvedValue([{ id: 1 }]),
        }),
      }),
    }),
    delete: vi.fn().mockReturnValue({
      where: vi.fn().mockResolvedValue(undefined),
    }),
  }),
}));

vi.mock("../../server/middleware/agentAuth", () => ({
  getAgentFromCookie: vi.fn().mockResolvedValue(null),
}));

vi.mock("../../server/_core/platformClient", () => ({
  floatPlatform: {
    utilize: vi.fn().mockResolvedValue({ success: true }),
    settle: vi.fn().mockResolvedValue({ success: true }),
    getBalance: vi.fn().mockResolvedValue(null),
    getTransactions: vi.fn().mockResolvedValue(null),
  },
  analyticsPlatform: {
    transactionSummary: vi.fn().mockResolvedValue(null),
  },
}));

vi.mock("../../server/_core/platformSettings", () => ({
  getPlatformSetting: vi.fn().mockResolvedValue("false"),
}));

vi.mock("../../server/_core/socketServer", () => ({
  getIO: vi.fn().mockReturnValue(null),
}));

vi.mock("../../server/_core/permify", () => ({
  permifyCheck: vi.fn().mockResolvedValue(true),
}));

vi.mock("../../server/tbClient", () => ({
  tbIsHealthy: vi.fn().mockResolvedValue(false),
  tbCreateTransfer: vi.fn().mockResolvedValue(null),
  tbEnsureAgentAccount: vi.fn().mockResolvedValue(true),
  tbGetAgentBalance: vi.fn().mockResolvedValue(null),
  tbGetSyncStatus: vi.fn().mockResolvedValue(null),
}));

vi.mock("bcryptjs", () => ({
  default: { compare: vi.fn(), hash: vi.fn().mockResolvedValue("$2b$10$hash") },
  compare: vi.fn(),
  hash: vi.fn().mockResolvedValue("$2b$10$hash"),
}));

vi.mock("jose", () => ({
  SignJWT: vi.fn().mockImplementation(function () {
    return {
      setProtectedHeader: vi.fn().mockReturnThis(),
      setIssuedAt: vi.fn().mockReturnThis(),
      setExpirationTime: vi.fn().mockReturnThis(),
      sign: vi.fn().mockResolvedValue("mock.jwt.token"),
    };
  }),
  jwtVerify: vi.fn().mockResolvedValue({
    payload: { sub: "1", role: "admin" },
  }),
  createRemoteJWKSet: vi.fn(),
}));

vi.mock("../../server/termii", () => ({
  sendSms: vi.fn().mockResolvedValue({ success: true }),
  buildConfirmationSms: vi.fn().mockReturnValue("msg"),
  buildReceiptSms: vi.fn().mockReturnValue("msg"),
}));

vi.mock("../../server/_core/velocityCheck", () => ({
  checkVelocity: vi.fn().mockResolvedValue({ allowed: true }),
}));

vi.mock("../../server/_core/fraudDetection", () => ({
  createFraudAlert: vi.fn().mockResolvedValue(undefined),
}));

function makeAdminCtx(): TrpcContext {
  return {
    req: {
      headers: { cookie: "session=mock.jwt.token" },
      cookies: {},
    } as any,
    res: {
      setHeader: vi.fn(),
      getHeader: vi.fn(),
      cookie: vi.fn(),
      clearCookie: vi.fn(),
    } as any,
    user: { id: "admin-1", role: "admin", tenantId: "tenant-1", name: "Admin" },
    agent: null,
  };
}

function makeUnauthCtx(): TrpcContext {
  return {
    req: { headers: {}, cookies: {} } as any,
    res: {
      setHeader: vi.fn(),
      getHeader: vi.fn(),
      cookie: vi.fn(),
      clearCookie: vi.fn(),
    } as any,
    user: null,
    agent: null,
  };
}

describe("Admin Dashboard Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("adminDashboard.systemStats", () => {
    it("returns system statistics for admin users", async () => {
      const caller = appRouter.createCaller(makeAdminCtx());
      const result = await caller.adminDashboard.getSystemStats();
      expect(result).toBeDefined();
      expect(typeof result.totalUsers).toBe("number");
    });

    it("rejects unauthenticated requests", async () => {
      const caller = appRouter.createCaller(makeUnauthCtx());
      await expect(caller.adminDashboard.getSystemStats()).rejects.toThrow();
    });
  });

  describe("adminDashboard.listUsers", () => {
    it("returns paginated user list", async () => {
      const caller = appRouter.createCaller(makeAdminCtx());
      const result = await caller.adminDashboard.listUsers({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.users)).toBe(true);
      expect(typeof result.total).toBe("number");
    });

    it("rejects unauthenticated requests", async () => {
      const caller = appRouter.createCaller(makeUnauthCtx());
      await expect(
        caller.adminDashboard.listUsers({ limit: 10, offset: 0 })
      ).rejects.toThrow();
    });
  });

  describe("adminDashboard.auditLog", () => {
    it("returns audit log entries", async () => {
      const caller = appRouter.createCaller(makeAdminCtx());
      const result = await caller.adminDashboard.getAuditLog({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.entries)).toBe(true);
    });
  });
});

describe("Health Check Integration", () => {
  it("status returns service health with timestamps", async () => {
    const caller = appRouter.createCaller(makeAdminCtx());
    const result = await caller.healthCheck.status();
    expect(result.timestamp).toBeDefined();
    expect(result.uptime).toBeGreaterThanOrEqual(0);
    expect(result.services).toBeDefined();
    expect(result.totalServices).toBeGreaterThan(0);
  });

  it("microservices returns service list", async () => {
    const caller = appRouter.createCaller(makeAdminCtx());
    const result = await caller.healthCheck.microservices();
    expect(result.services).toBeDefined();
    expect(Array.isArray(result.services)).toBe(true);
    expect(result.services.length).toBeGreaterThan(0);
    for (const svc of result.services) {
      expect(svc.name).toBeDefined();
      expect(svc.type).toBeDefined();
      expect(svc.port).toBeDefined();
      expect(["healthy", "unhealthy", "unavailable"]).toContain(svc.status);
    }
  });
});
