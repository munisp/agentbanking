/**
 * bulkTransactionProcessor.cancelBatch — funds-flow unit tests.
 *
 * Covers NF-FF-6 behavior in server/routers/bulkTransactionProcessor.ts:
 *  - admin-only: non-admin → FORBIDDEN, unauthenticated → UNAUTHORIZED
 *  - id-less invocation (the old mass-assign caller-data path) → BAD_REQUEST
 *  - conditional cancel: 0 rows (not found / not pending) → 409 CONFLICT
 *  - happy path cancels exactly one pending transaction
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

vi.mock("../../lib/auditTrail", () => ({ logAudit: vi.fn(() => ({})) }));

vi.mock("drizzle-orm", async () => {
  const { drizzleOrmStub } = await import("./fundsFlowTestKit");
  return drizzleOrmStub();
});
vi.mock("../../../drizzle/schema", async () => {
  const { drizzleSchemaStub } = await import("./fundsFlowTestKit");
  return drizzleSchemaStub();
});

import { bulkTransactionProcessorRouter } from "../bulkTransactionProcessor";
import { makeCtx } from "./fundsFlowTestKit";

function makeDb(executeResult: unknown) {
  return { execute: vi.fn(async () => executeResult) };
}

beforeEach(() => {
  h.state.db = null;
});

describe("bulkTransactionProcessor.cancelBatch", () => {
  it("non-admin caller → FORBIDDEN before touching the DB", async () => {
    const db = makeDb({ rows: [{ id: 5 }] });
    h.state.db = db;
    const caller = bulkTransactionProcessorRouter.createCaller(makeCtx("user"));

    await expect(caller.cancelBatch({ id: 5 })).rejects.toMatchObject({
      code: "FORBIDDEN",
    });
    expect(db.execute).not.toHaveBeenCalled();
  });

  it("unauthenticated caller → UNAUTHORIZED", async () => {
    const db = makeDb({ rows: [{ id: 5 }] });
    h.state.db = db;
    const ctx = { ...makeCtx("admin"), user: null };
    const caller = bulkTransactionProcessorRouter.createCaller(ctx);

    await expect(caller.cancelBatch({ id: 5 })).rejects.toMatchObject({
      code: "UNAUTHORIZED",
    });
    expect(db.execute).not.toHaveBeenCalled();
  });

  it("missing id → BAD_REQUEST (caller data is never written to the ledger)", async () => {
    const db = makeDb({ rows: [] });
    h.state.db = db;
    const caller = bulkTransactionProcessorRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.cancelBatch({ data: { amount: 999999, status: "success" } })
    ).rejects.toMatchObject({
      code: "BAD_REQUEST",
      message: expect.stringContaining("requires a transaction id"),
    });
    expect(db.execute).not.toHaveBeenCalled();
  });

  it("0 rows from the conditional cancel (not pending / not found) → 409 CONFLICT", async () => {
    const db = makeDb({ rows: [] });
    h.state.db = db;
    const caller = bulkTransactionProcessorRouter.createCaller(makeCtx("admin"));

    await expect(caller.cancelBatch({ id: 5 })).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("not in a cancellable"),
    });
  });

  it("happy path: exactly one pending transaction is cancelled", async () => {
    const db = makeDb({ rows: [{ id: 5 }] });
    h.state.db = db;
    const caller = bulkTransactionProcessorRouter.createCaller(makeCtx("admin"));

    const result: any = await caller.cancelBatch({ id: 5 });

    expect(db.execute).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({ success: true, id: 5 });
  });
});
