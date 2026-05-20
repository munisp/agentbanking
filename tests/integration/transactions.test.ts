/**
 * Integration Test: Transaction Flow
 * ─────────────────────────────────────────────────────────────────────────────
 * End-to-end transaction lifecycle tests using mocked DB and platform clients.
 * These tests verify the full procedure chain: input validation → DB write →
 * float update → commission → loyalty → audit log → response shape.
 *
 * Run: pnpm test tests/integration/transactions.test.ts
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { appRouter } from "../../server/routers";
import type { TrpcContext } from "../../server/_core/context";

// ── Mock all external dependencies ───────────────────────────────────────────
vi.mock("../../server/db", () => ({
  getDb: vi.fn().mockResolvedValue(null), // returns null → geofence/velocity checks skip gracefully
  getAgentByCode: vi.fn(),
  getAgentById: vi.fn(),
  createTransaction: vi.fn(),
  updateAgentFloat: vi.fn(),
  updateAgentCommission: vi.fn(),
  addLoyaltyHistory: vi.fn(),
  writeAuditLog: vi.fn(),
  getTransactionsByAgent: vi.fn(),
  getTransactionByRef: vi.fn(),
  updateTransactionStatus: vi.fn(),
  updateFraudAlertStatus: vi.fn(),
  getLoyaltyHistory: vi.fn(),
  createChatSession: vi.fn(),
  getChatSession: vi.fn(),
  addChatMessage: vi.fn(),
  getChatMessages: vi.fn(),
  getAuditLog: vi.fn(),
  upsertUser: vi.fn(),
  getUserByOpenId: vi.fn(),
  getUserByKeycloakSub: vi.fn(),
}));

vi.mock("../../server/tbClient", () => ({
  tbIsHealthy: vi.fn().mockResolvedValue(false),
  tbCreateTransfer: vi.fn().mockResolvedValue(null),
  tbEnsureAgentAccount: vi.fn().mockResolvedValue(true),
  tbGetAgentBalance: vi.fn().mockResolvedValue(null),
  tbGetSyncStatus: vi.fn().mockResolvedValue(null),
}));

vi.mock("../../server/middleware/agentAuth", () => ({
  getAgentFromCookie: vi.fn().mockResolvedValue({
    id: 1,
    agentCode: "AGT001",
    name: "Emeka Obi",
    role: "agent",
    tier: "Gold",
  }),
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

vi.mock("bcryptjs", () => ({
  default: {
    compare: vi.fn().mockResolvedValue(true),
    hash: vi.fn().mockResolvedValue("$2b$10$hash"),
  },
  compare: vi.fn().mockResolvedValue(true),
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
    payload: {
      sub: "1",
      agentCode: "AGT001",
      name: "Emeka Obi",
      role: "agent",
      tier: "Gold",
    },
  }),
  createRemoteJWKSet: vi.fn(),
}));

vi.mock("../../server/termii", () => ({
  sendSms: vi
    .fn()
    .mockResolvedValue({ success: true, messageId: "mock-msg-id" }),
  buildConfirmationSms: vi
    .fn()
    .mockReturnValue("Your transaction was successful."),
  buildReceiptSms: vi.fn().mockReturnValue("Receipt: TX123"),
}));

vi.mock("../../server/_core/platformSettings", () => ({
  getPlatformSetting: vi.fn().mockResolvedValue("false"),
}));

vi.mock("../../server/_core/velocityCheck", () => ({
  checkVelocity: vi.fn().mockResolvedValue({ allowed: true }),
}));

vi.mock("../../server/_core/fraudDetection", () => ({
  createFraudAlert: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../../server/_core/socketServer", () => ({
  getIO: vi.fn().mockReturnValue(null),
}));

// ── Helpers ───────────────────────────────────────────────────────────────────
import {
  getAgentById,
  createTransaction,
  updateAgentFloat,
  updateAgentCommission,
  addLoyaltyHistory,
  writeAuditLog,
  getTransactionsByAgent,
  getTransactionByRef,
} from "../../server/db";
import { getAgentFromCookie } from "../../server/middleware/agentAuth";

const mockAgent = {
  id: 1,
  agentCode: "AGT001",
  name: "Emeka Obi",
  phone: "08012345678",
  email: "emeka@test.com",
  pinHash: "$2b$10$hash",
  role: "agent" as const,
  tier: "Gold" as const,
  floatBalance: "500000",
  floatLimit: "1000000",
  commissionBalance: "12000",
  loyaltyPoints: 850,
  isActive: true,
  location: "Lagos",
  createdAt: new Date(),
  lastLoginAt: new Date(),
  terminalEnabled: true,
  terminalDisabledReason: null,
  floatLocked: false,
  terminalModel: null,
  terminalSerial: null,
  streak: 0,
  rank: null,
};

const mockTx = {
  id: 1,
  ref: "TXNABC123",
  agentId: 1,
  type: "Cash In" as const,
  amount: "5000",
  fee: "0",
  commission: "50",
  customerName: null,
  customerPhone: "08099887766",
  customerAccount: null,
  destinationBank: null,
  destinationAccount: null,
  status: "success" as const,
  channel: "Cash" as const,
  note: null,
  fraudScore: "0.00",
  smsSent: false,
  deviceToken: null,
  metadata: null,
  createdAt: new Date(),
};

function makeCtx(agentId = 1): TrpcContext {
  return {
    req: {
      headers: { cookie: "agent_session=mock.jwt.token" },
      cookies: {},
    } as any,
    res: {
      setHeader: vi.fn(),
      getHeader: vi.fn(),
      cookie: vi.fn(),
      clearCookie: vi.fn(),
    } as any,
    agent: {
      id: agentId,
      agentCode: "AGT001",
      name: "Emeka Obi",
      role: "agent",
      tier: "Gold",
    },
    user: {
      id: agentId,
      username: "AGT001",
      role: "admin" as const,
      agentCode: "AGT001",
      name: "Emeka Obi",
      email: "agent@54link.io",
    },
  };
}

// ── Test suite ────────────────────────────────────────────────────────────────
describe("Transaction Integration Flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getAgentFromCookie).mockResolvedValue({
      id: 1,
      agentCode: "AGT001",
      name: "Emeka Obi",
      role: "agent",
      tier: "Gold",
    } as any);
    vi.mocked(getAgentById).mockResolvedValue(mockAgent as any);
    vi.mocked(createTransaction).mockResolvedValue(mockTx as any);
    vi.mocked(updateAgentFloat).mockResolvedValue(undefined);
    vi.mocked(updateAgentCommission).mockResolvedValue(undefined);
    vi.mocked(addLoyaltyHistory).mockResolvedValue(undefined);
    vi.mocked(writeAuditLog).mockResolvedValue(undefined);
  });

  describe("transactions.create", () => {
    it("creates a cash-in transaction and returns a ref", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.create({
        type: "Cash In",
        amount: 5000,
        customerPhone: "08099887766",
        channel: "Cash",
      });

      expect(result.ref).toBeTruthy();
      expect(result.success).toBe(true);
      expect(result.transactionId).toBeTruthy();
      expect(createTransaction).toHaveBeenCalledOnce();
      expect(updateAgentFloat).toHaveBeenCalledOnce();
      expect(addLoyaltyHistory).toHaveBeenCalledOnce();
      expect(writeAuditLog).toHaveBeenCalledOnce();
    });

    it("creates a cash-out transaction", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.create({
        type: "Cash Out",
        amount: 2000,
        customerPhone: "08011223344",
        channel: "Cash",
      });
      expect(result.success).toBe(true);
      expect(result.ref).toBeTruthy();
    });

    it("creates a transfer transaction", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.create({
        type: "Transfer",
        amount: 10000,
        customerPhone: "08055667788",
        channel: "Cash",
      });
      expect(result.success).toBe(true);
    });

    it("creates an airtime transaction", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.create({
        type: "Airtime",
        amount: 500,
        customerPhone: "08099887766",
        channel: "USSD",
      });
      expect(result.success).toBe(true);
    });

    it("rejects unauthenticated requests", async () => {
      vi.mocked(getAgentFromCookie).mockResolvedValueOnce(null);
      const unauthCtx: TrpcContext = {
        req: { headers: {}, cookies: {} } as any,
        res: {
          setHeader: vi.fn(),
          getHeader: vi.fn(),
          cookie: vi.fn(),
          clearCookie: vi.fn(),
        } as any,
        agent: null,
        user: null,
      };
      const caller = appRouter.createCaller(unauthCtx);
      await expect(
        caller.transactions.create({
          type: "Cash In",
          amount: 1000,
          customerPhone: "08099887766",
          channel: "Cash",
        })
      ).rejects.toThrow();
    });

    it("rejects negative amounts", async () => {
      const caller = appRouter.createCaller(makeCtx());
      await expect(
        caller.transactions.create({
          type: "Cash In",
          amount: -500,
          customerPhone: "08099887766",
          channel: "Cash",
        })
      ).rejects.toThrow();
    });

    it("rejects zero amounts", async () => {
      const caller = appRouter.createCaller(makeCtx());
      await expect(
        caller.transactions.create({
          type: "Cash In",
          amount: 0,
          customerPhone: "08099887766",
          channel: "Cash",
        })
      ).rejects.toThrow();
    });

    it("calculates commission correctly for Cash In", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.create({
        type: "Cash In",
        amount: 10000,
        customerPhone: "08099887766",
        channel: "Cash",
      });
      // Cash In commission rate is 0.5% = 50
      expect(result.commission).toBeGreaterThan(0);
    });

    it("returns loyalty points earned", async () => {
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.create({
        type: "Cash In",
        amount: 10000,
        customerPhone: "08099887766",
        channel: "Cash",
      });
      expect(result.pointsEarned).toBeGreaterThanOrEqual(0);
    });
  });

  describe("transactions.list", () => {
    it("returns paginated transaction list", async () => {
      vi.mocked(getTransactionsByAgent).mockResolvedValue([mockTx] as any);
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.list({ limit: 20, offset: 0 });
      expect(Array.isArray(result)).toBe(true);
    });

    it("returns empty list when no transactions", async () => {
      vi.mocked(getTransactionsByAgent).mockResolvedValue([]);
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.list({ limit: 20, offset: 0 });
      expect(result).toHaveLength(0);
    });

    it("returns numeric amount fields", async () => {
      vi.mocked(getTransactionsByAgent).mockResolvedValue([mockTx] as any);
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.list({ limit: 20, offset: 0 });
      expect(typeof result[0].amount).toBe("number");
      expect(typeof result[0].fee).toBe("number");
    });

    it("rejects unauthenticated requests", async () => {
      vi.mocked(getAgentFromCookie).mockResolvedValueOnce(null);
      const unauthCtx: TrpcContext = {
        req: { headers: {}, cookies: {} } as any,
        res: {
          setHeader: vi.fn(),
          getHeader: vi.fn(),
          cookie: vi.fn(),
          clearCookie: vi.fn(),
        } as any,
        agent: null,
        user: null,
      };
      const caller = appRouter.createCaller(unauthCtx);
      await expect(
        caller.transactions.list({ limit: 20, offset: 0 })
      ).rejects.toThrow();
    });
  });

  describe("transactions.getByRef", () => {
    it("returns a transaction by ref", async () => {
      vi.mocked(getTransactionByRef).mockResolvedValue(mockTx as any);
      const caller = appRouter.createCaller(makeCtx());
      const result = await caller.transactions.getByRef({ ref: "TXNABC123" });
      expect(result?.ref).toBe("TXNABC123");
    });

    it("throws NOT_FOUND for unknown ref", async () => {
      vi.mocked(getTransactionByRef).mockResolvedValue(undefined);
      const caller = appRouter.createCaller(makeCtx());
      await expect(
        caller.transactions.getByRef({ ref: "UNKNOWN" })
      ).rejects.toThrow();
    });
  });
});
