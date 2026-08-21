/**
 * floatReconciliationsCrud — funds-flow unit tests.
 *
 * Covers NF-FF-24 behavior in server/routers/floatReconciliationsCrud.ts:
 *  - create always opens a reconciliation as "open" — no auto-resolve shortcut,
 *    even for zero/tiny variances; severity is computed from variance %
 *  - resolve is admin-only and conditional: 0 rows → 409 CONFLICT
 *  - resolver identity comes from the session (ctx.user.id), never input
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

import { floatReconciliationsRouter } from "../floatReconciliationsCrud";
import { makeCtx } from "./fundsFlowTestKit";

function makeDb(opts: { insertedRows?: unknown[]; updatedRows?: unknown[] }) {
  const capture = { inserted: [] as any[], setValues: [] as any[] };
  const db = {
    insert: vi.fn(() => ({
      values: (v: any) => {
        capture.inserted.push(v);
        return { returning: async () => opts.insertedRows ?? [] };
      },
    })),
    update: vi.fn(() => ({
      set: (v: any) => {
        capture.setValues.push(v);
        return { where: () => ({ returning: async () => opts.updatedRows ?? [] }) };
      },
    })),
  };
  return { db, capture };
}

beforeEach(() => {
  h.state.db = null;
});

describe("floatReconciliationsCrud.create", () => {
  it("always creates with status 'open' — even a zero variance is not auto-resolved", async () => {
    const { db, capture } = makeDb({ insertedRows: [{ id: 9 }] });
    h.state.db = db;
    const caller = floatReconciliationsRouter.createCaller(makeCtx("user"));

    const result: any = await caller.create({
      agentId: 7,
      expectedBalance: "10000.00",
      actualBalance: "10000.00",
    });

    expect(capture.inserted[0].status).toBe("open");
    expect(capture.inserted[0].discrepancy).toBe("0.00");
    expect(result.severity).toBe("normal");
    expect(result.variancePercent).toBe(0);
  });

  it("flags >5% variance as critical while still creating 'open'", async () => {
    const { db, capture } = makeDb({ insertedRows: [{ id: 10 }] });
    h.state.db = db;
    const caller = floatReconciliationsRouter.createCaller(makeCtx("user"));

    const result: any = await caller.create({
      agentId: 7,
      expectedBalance: "10000.00",
      actualBalance: "11000.00",
    });

    expect(capture.inserted[0].status).toBe("open");
    expect(capture.inserted[0].discrepancy).toBe("1000.00");
    expect(result.severity).toBe("critical");
    expect(result.variancePercent).toBe(10);
  });
});

describe("floatReconciliationsCrud.resolve", () => {
  it("happy path: admin resolves; resolver id comes from the session", async () => {
    const row = {
      id: 3,
      status: "resolved",
      resolvedBy: 1,
      resolvedAt: new Date(),
    };
    const { db, capture } = makeDb({ updatedRows: [row] });
    h.state.db = db;
    const caller = floatReconciliationsRouter.createCaller(makeCtx("admin"));

    const result: any = await caller.resolve({
      id: 3,
      notes: "verified against settlement file",
    });

    expect(result.message).toBe("Reconciliation resolved");
    // ctx.user.id === 1 from makeCtx — never caller-supplied.
    expect(capture.setValues[0].resolvedBy).toBe(1);
    expect(capture.setValues[0].status).toBe("resolved");
  });

  it("already-resolved or unknown record (0 rows) → 409 CONFLICT", async () => {
    const { db } = makeDb({ updatedRows: [] });
    h.state.db = db;
    const caller = floatReconciliationsRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.resolve({ id: 3, notes: "second resolve attempt" })
    ).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("already resolved"),
    });
  });

  it("non-admin caller → FORBIDDEN before touching the DB", async () => {
    const { db } = makeDb({ updatedRows: [{ id: 3 }] });
    h.state.db = db;
    const caller = floatReconciliationsRouter.createCaller(makeCtx("user"));

    await expect(
      caller.resolve({ id: 3, notes: "not allowed" })
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
    expect(db.update).not.toHaveBeenCalled();
  });
});
