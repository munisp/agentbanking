/**
 * transactionReconciliation — funds-flow unit tests.
 *
 * Covers NF-FF-19 behavior in server/routers/transactionReconciliation.ts:
 *  - enforceTransition rejects any target outside {flagged, under_review,
 *    resolved_note} — value statuses (success/reversed/disputed/resolved) can
 *    never be written from the reconciliation workflow
 *  - the conditional update guards final-state rows: 0 rows → 409 CONFLICT
 *  - markDisputed writes status "flagged" (+ dispute metadata), never "disputed"
 *  - markResolved writes status "resolved_note", never "resolved"
 *  - admin-only procedures: non-admin → FORBIDDEN
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

import { transactionReconciliationRouter } from "../transactionReconciliation";
import { makeCtx } from "./fundsFlowTestKit";

const RECORD = { id: 5, status: "initiated", metadata: null };

function makeDb(opts: { record?: any; updatedRows?: unknown[] }) {
  const capture = { setValues: [] as any[] };
  const db = {
    select: vi.fn(() => ({
      from: () => ({
        where: () => ({ limit: async () => (opts.record ? [opts.record] : []) }),
      }),
    })),
    update: vi.fn(() => ({
      set: (v: any) => {
        capture.setValues.push(v);
        return {
          where: () => ({ returning: async () => opts.updatedRows ?? [] }),
        };
      },
    })),
  };
  return { db, capture };
}

beforeEach(() => {
  h.state.db = null;
});

describe("transactionReconciliation.updateStatus", () => {
  it.each(["flagged", "under_review", "resolved_note"])(
    "accepts reconciliation target status '%s'",
    async status => {
      const { db, capture } = makeDb({
        record: { ...RECORD },
        updatedRows: [{ ...RECORD, status }],
      });
      h.state.db = db;
      const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

      const result: any = await caller.updateStatus({ id: 5, status });
      expect(result.success).toBe(true);
      expect(capture.setValues[0].status).toBe(status);
    }
  );

  it.each(["success", "failed", "reversed", "disputed", "resolved", "completed"])(
    "rejects value/legacy target status '%s' with BAD_REQUEST",
    async status => {
      const { db } = makeDb({ record: { ...RECORD } });
      h.state.db = db;
      const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

      await expect(caller.updateStatus({ id: 5, status })).rejects.toMatchObject(
        {
          code: "BAD_REQUEST",
          message: expect.stringContaining(
            "only flagged, under_review, resolved_note are permitted targets"
          ),
        }
      );
      expect(db.update).not.toHaveBeenCalled();
    }
  );

  it("0 rows from the conditional update (final value state) → 409 CONFLICT", async () => {
    const { db } = makeDb({ record: { ...RECORD }, updatedRows: [] });
    h.state.db = db;
    const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.updateStatus({ id: 5, status: "flagged" })
    ).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("final value state"),
    });
  });

  it("missing transaction → NOT_FOUND", async () => {
    const { db } = makeDb({ record: null });
    h.state.db = db;
    const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.updateStatus({ id: 404, status: "flagged" })
    ).rejects.toMatchObject({ code: "NOT_FOUND" });
  });

  it("non-admin caller → FORBIDDEN before touching the DB", async () => {
    const { db } = makeDb({ record: { ...RECORD } });
    h.state.db = db;
    const caller = transactionReconciliationRouter.createCaller(makeCtx("user"));

    await expect(
      caller.updateStatus({ id: 5, status: "flagged" })
    ).rejects.toMatchObject({ code: "FORBIDDEN" });
    expect(db.select).not.toHaveBeenCalled();
  });
});

describe("transactionReconciliation.markDisputed", () => {
  it("writes status 'flagged' with dispute metadata (never the literal 'disputed')", async () => {
    const { db, capture } = makeDb({
      record: { ...RECORD, status: "completed" },
      updatedRows: [{ ...RECORD, status: "flagged" }],
    });
    h.state.db = db;
    const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

    const result: any = await caller.markDisputed({
      id: 5,
      reason: "customer claims non-receipt",
      disputeRef: "DSP-1",
    });

    expect(result.success).toBe(true);
    const set = capture.setValues[0];
    expect(set.status).toBe("flagged");
    expect(set.metadata.dispute).toMatchObject({
      reason: "customer claims non-receipt",
      disputeRef: "DSP-1",
      previousStatus: "completed",
    });
  });

  it("final-state transaction cannot be flagged → 409 CONFLICT", async () => {
    const { db } = makeDb({
      record: { ...RECORD, status: "success" },
      updatedRows: [],
    });
    h.state.db = db;
    const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

    await expect(
      caller.markDisputed({ id: 5, reason: "too late" })
    ).rejects.toMatchObject({ code: "CONFLICT" });
  });
});

describe("transactionReconciliation.markResolved", () => {
  it("writes status 'resolved_note' with resolution metadata (never 'resolved')", async () => {
    const { db, capture } = makeDb({
      record: { ...RECORD, status: "flagged" },
      updatedRows: [{ ...RECORD, status: "resolved_note" }],
    });
    h.state.db = db;
    const caller = transactionReconciliationRouter.createCaller(makeCtx("admin"));

    const result: any = await caller.markResolved({
      id: 5,
      resolution: "manual review confirmed the credit",
    });

    expect(result.success).toBe(true);
    const set = capture.setValues[0];
    expect(set.status).toBe("resolved_note");
    expect(set.metadata.resolution).toMatchObject({
      note: "manual review confirmed the credit",
      previousStatus: "flagged",
    });
  });
});
