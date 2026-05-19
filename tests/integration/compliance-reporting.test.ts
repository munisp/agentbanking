/**
 * Integration Test: Compliance & Reporting
 * Tests CBN reporting, GDPR, AML, audit trails, and regulatory features.
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
  analyticsPlatform: { transactionSummary: vi.fn().mockResolvedValue(null) },
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
  jwtVerify: vi
    .fn()
    .mockResolvedValue({ payload: { sub: "1", role: "admin" } }),
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
    req: { headers: { cookie: "session=mock.jwt.token" }, cookies: {} } as any,
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

describe("CBN Reporting Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("cbnReporting.list returns reports", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.cbnReporting.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("cbnReporting.list rejects unauthenticated", async () => {
    const caller = appRouter.createCaller(makeUnauthCtx());
    await expect(
      caller.cbnReporting.list({ limit: 10, offset: 0 })
    ).rejects.toThrow();
  });
});

describe("GDPR Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("gdpr.list returns GDPR records", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.gdpr.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("gdpr.list rejects unauthenticated", async () => {
    const caller = appRouter.createCaller(makeUnauthCtx());
    await expect(caller.gdpr.list({ limit: 10, offset: 0 })).rejects.toThrow();
  });
});

describe("Data Consent Records Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("dataConsentRecordsCrud.list returns consent records", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.dataConsentRecordsCrud.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Compliance Certificate Manager Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("complianceCertManager.list returns certificates", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.complianceCertManager.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("complianceCertManager.list rejects unauthenticated", async () => {
    const caller = appRouter.createCaller(makeUnauthCtx());
    await expect(
      caller.complianceCertManager.list({ limit: 10, offset: 0 })
    ).rejects.toThrow();
  });
});

describe("Billing Audit Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("billingAudit.list returns audit records", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.billingAudit.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("billingAudit.list rejects unauthenticated", async () => {
    const caller = appRouter.createCaller(makeUnauthCtx());
    await expect(
      caller.billingAudit.list({ limit: 10, offset: 0 })
    ).rejects.toThrow();
  });
});

describe("AML Screening Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("amlScreening.list returns screening records", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.amlScreening.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Advanced Audit Log Viewer Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("advancedAuditLogViewer.list returns audit entries", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.advancedAuditLogViewer.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Financial Reconciliation Dashboard Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("financialReconciliationDash.list returns reconciliation data", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.financialReconciliationDash.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});
