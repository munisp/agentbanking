/**
 * settlementNettingEngine.settleSession — funds-flow unit tests.
 *
 * Covers NF-FF-16 behavior in server/routers/settlementNettingEngine.ts:
 *  - unparseable / non-positive session ids (numId ≤ 0) → 400 BAD_REQUEST
 *    (previously these silently settled a non-existent row and returned a
 *    fabricated confirmation)
 *  - conditional transition: 0 rows updated (unknown id or already settled)
 *    → 409 CONFLICT, no fabricated confirmation
 *  - happy path returns a real confirmation
 *  - admin-only: non-admin → FORBIDDEN
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

const h = vi.hoisted(() => {
  const state: { db: any } = { db: null };
  return { state };
});

vi.mock("../../db", () => ({
  getDb: vi.fn(async () => h.state.db),
  writeAuditLog: vi.fn(async () => ({})),
}));

vi.mock("../../_core/permify", () => ({
  permifyCheck: vi.fn(async () => true),
}));

vi.mock("../../_core/logger", () => ({
  default: { warn: vi.fn(), info: vi.fn(), error: vi.fn(), debug: vi.fn() },
  __esModule: true,
}));

vi.mock("../../middleware/sidecarIntegration", async () => {
  const { passThroughMiddleware } = await import("./fundsFlowTestKit");
  return { createSidecarMiddleware: passThroughMiddleware };
});
vi.mock("../../middleware/trpcCacheMiddleware", async () => {
  const { passThroughMiddleware } = await import("./fundsFlowTestKit");
  return { createTrpcCacheMiddleware: passThroughMiddleware };
});
vi.mock("../../middleware/productionHardeningMiddleware", async () => {
  const { passThroughMiddleware } = await import("./fundsFlowTestKit");
  return { createProductionHardeningMiddleware: passThroughMiddleware };
});

vi.mock("../../kafkaClient", () => ({ publishEvent: vi.fn(async () => {}) }));
vi.mock("../../redisClient", () => ({
  cacheSet: vi.fn(async () => {}),
  cacheGet: vi.fn(async () => null),
}));
vi.mock("../../tbClient", () => ({ tbCreateTransfer: vi.fn(async () => ({})) }));
vi.mock("../../fluvio", () => ({ fluvioProduce: vi.fn(async () => ({})) }));
vi.mock("../../lib/auditTrail", () => ({ logAudit: vi.fn(() => ({})) }));

vi.mock("drizzle-orm", async () => {
  const { drizzleOrmStub } = await import("./fundsFlowTestKit");
  return drizzleOrmStub();
});
vi.mock("../../../drizzle/schema", async () => {
  const { drizzleSchemaStub } = await import("./fundsFlowTestKit");
  return drizzleSchemaStub();
});

import { settlementNettingEngineRouter } from "../settlementNettingEngine";
import { makeCtx } from "./fundsFlowTestKit";

function makeDb(updatedRows: unknown[]) {
  const capture = { setValues: [] as any[] };
  const db = {
    update: vi.fn(() => ({
      set: (v: any) => {
        capture.setValues.push(v);
        return { where: () => ({ returning: async () => updatedRows }) };
      },
    })),
  };
  return { db, capture };
}

beforeEach(() => {
  h.state.db = null;
});

describe("settlementNettingEngine.settleSession", () => {
  it.each(["0", "NET-0", "garbage", ""])(
    "rejects non-positive/unparseable session id '%s' → BAD_REQUEST, no DB write",
    async sessionId => {
      const { db } = makeDb([{ id: 1 }]);
      h.state.db = db;
      const caller = settlementNettingEngineRouter.createCaller(makeCtx("admin"));

      await expect(caller.settleSession({ sessionId })).rejects.toMatchObject({
        code: "BAD_REQUEST",
        message: expect.stringContaining("Invalid settlement session id"),
      });
      expect(db.update).not.toHaveBeenCalled();
    }
  );

  it("conditional update returning 0 rows (unknown id or already settled) → 409 CONFLICT", async () => {
    const { db } = makeDb([]);
    h.state.db = db;
    const caller = settlementNettingEngineRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.settleSession({ sessionId: "NET-12" })
    ).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("not in 'calculating' status"),
    });
  });

  it("happy path: settling a 'calculating' session returns a real confirmation", async () => {
    const { db, capture } = makeDb([{ id: 12 }]);
    h.state.db = db;
    const caller = settlementNettingEngineRouter.createCaller(makeCtx("admin"));

    const result: any = await caller.settleSession({ sessionId: "NET-12" });

    expect(db.update).toHaveBeenCalledTimes(1);
    expect(capture.setValues[0].status).toBe("settled");
    expect(result).toMatchObject({ sessionId: "NET-12", status: "settled" });
    expect(result.confirmationRef).toMatch(/^SREF-/);
    expect(typeof result.settledAt).toBe("string");
  });

  it("non-admin caller → FORBIDDEN before touching the DB", async () => {
    const { db } = makeDb([{ id: 12 }]);
    h.state.db = db;
    const caller = settlementNettingEngineRouter.createCaller(makeCtx("user"));

    await expect(
      caller.settleSession({ sessionId: "NET-12" })
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
    expect(db.update).not.toHaveBeenCalled();
  });

  it("database unavailable → INTERNAL_SERVER_ERROR", async () => {
    h.state.db = null;
    const caller = settlementNettingEngineRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.settleSession({ sessionId: "NET-12" })
    ).rejects.toMatchObject({ code: "INTERNAL_SERVER_ERROR" });
  });
});
