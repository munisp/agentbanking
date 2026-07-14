/**
 * Integration Test: Infrastructure & Platform Services
 * Tests workflow engine, config management, rate limiting, notifications, resilience.
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

describe("Workflow Engine Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("workflowEngine.list returns workflows", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.workflowEngine.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("workflowEngine.list rejects unauthenticated", async () => {
    const caller = appRouter.createCaller(makeUnauthCtx());
    await expect(
      caller.workflowEngine.list({ limit: 10, offset: 0 })
    ).rejects.toThrow();
  });
});

describe("Config Management Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("configManagement.list returns configs", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.configManagement.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });

  it("configManagement.list rejects unauthenticated", async () => {
    const caller = appRouter.createCaller(makeUnauthCtx());
    await expect(
      caller.configManagement.list({ limit: 10, offset: 0 })
    ).rejects.toThrow();
  });
});

describe("Rate Limit Engine Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("rateLimitEngine.list returns rate limit rules", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.rateLimitEngine.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Multi-Channel Notification Hub Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("multiChannelNotificationHub.list returns notifications", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.multiChannelNotificationHub.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Resilience Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("resilience.list returns resilience configs", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.resilience.list({ limit: 10, offset: 0 });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("SLA Monitoring Dashboard Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("slaMonitoringDash.list returns SLA records", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.slaMonitoringDash.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Intelligent Routing Engine Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("intelligentRoutingEngine.list returns routing rules", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.intelligentRoutingEngine.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Platform Maturity Scorecard Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("platformMaturityScorecard.list returns scorecard data", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.platformMaturityScorecard.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Training Certification Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("trainingCertification.list returns certifications", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.trainingCertification.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Partner Self-Service Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("partnerSelfService.list returns partner records", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.partnerSelfService.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});

describe("Currency Hedging Integration", () => {
  beforeEach(() => vi.clearAllMocks());

  it("currencyHedging.list returns hedging positions", async () => {
    const caller = appRouter.createCaller(makeCtx());
    const result = await caller.currencyHedging.list({
      limit: 10,
      offset: 0,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.items)).toBe(true);
  });
});
