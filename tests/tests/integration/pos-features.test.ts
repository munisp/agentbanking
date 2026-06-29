/**
 * Integration Test: POS Features
 * Tests float management, transactions, commissions, QR payments, receipts.
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
          limit: vi.fn().mockResolvedValue([{ cnt: 0 }]),
        }),
        orderBy: vi.fn().mockReturnValue({
          limit: vi.fn().mockReturnValue({
            offset: vi.fn().mockResolvedValue([]),
          }),
        }),
        limit: vi.fn().mockResolvedValue([{ cnt: 0, t: "0" }]),
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
  SignJWT: vi.fn().mockImplementation(() => ({
    setProtectedHeader: vi.fn().mockReturnThis(),
    setIssuedAt: vi.fn().mockReturnThis(),
    setExpirationTime: vi.fn().mockReturnThis(),
    sign: vi.fn().mockResolvedValue("mock.jwt.token"),
  })),
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

function makeCtx(): TrpcContext {
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

describe("POS Features Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("agentFloatTransfer", () => {
    it("list returns array with pagination", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentFloatTransfer.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
      expect(typeof result.total).toBe("number");
    });
  });

  describe("agentCommissionCalc", () => {
    it("summary returns commission stats", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentCommissionCalc.summary();
      expect(result).toBeDefined();
    });
  });

  describe("dynamicQrPayment", () => {
    it("list returns QR payment records", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.dynamicQrPayment.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("receiptTemplates", () => {
    it("list returns receipt templates", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.receiptTemplates.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("agentPerformanceScorecard", () => {
    it("list returns scorecard data", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentPerformanceScorecard.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("agentGamification", () => {
    it("list returns gamification data", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentGamification.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("commissionClawback", () => {
    it("list returns clawback records", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.commissionClawback.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
    });
  });
});

describe("Agent Management Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("agentOnboarding", () => {
    it("list returns onboarding records", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentOnboarding.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("agentHierarchy", () => {
    it("list returns hierarchy data", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentHierarchy.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("agentBanking", () => {
    it("list returns banking accounts", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentBanking.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("agentKyc", () => {
    it("list returns KYC records", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentKyc.list({ limit: 10, offset: 0 });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });

  describe("agentInventoryMgmt", () => {
    it("list returns inventory records", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.agentInventoryMgmt.list({
        limit: 10,
        offset: 0,
      });
      expect(result).toBeDefined();
      expect(Array.isArray(result.items)).toBe(true);
    });
  });
});
