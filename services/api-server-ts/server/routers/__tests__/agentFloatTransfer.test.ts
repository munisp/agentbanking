/**
 * agentFloatTransfer.transfer — funds-flow unit tests.
 *
 * Covers NF-FF-10 behavior in server/routers/agentFloatTransfer.ts:
 *  - guarded conditional sender debit returning 0 rows aborts the transfer
 *    (error raised inside the single ACID transaction; recipient is never
 *    credited and no ledger row is written)
 *  - happy path: debit + credit + ledger row in one transaction
 *  - self-transfer rejected
 *  - idempotency: replay returns cached result; different payload → 409
 *
 * Infrastructure is mocked at the module boundary; router + transactionHelper
 * execute for real.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

const h = vi.hoisted(() => {
  const state: { db: any; session: any } = { db: null, session: null };
  return { state };
});

vi.mock("../../db", () => ({
  getDb: vi.fn(async () => h.state.db),
  writeAuditLog: vi.fn(async () => ({})),
  getAgentById: vi.fn(async () => null),
}));

vi.mock("../../middleware/agentAuth", () => ({
  getAgentFromCookie: vi.fn(async () => h.state.session),
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

import { agentFloatTransferRouter } from "../agentFloatTransfer";
import { hashIdempotencyPayload } from "../../lib/transactionHelper";
import { makeCtx } from "./fundsFlowTestKit";

const SENDER = {
  id: 7,
  agentCode: "AGT-000007",
  name: "Sender",
  tier: "1",
  role: "agent",
};
const RECIPIENT = { id: 8, agentCode: "AGT-000008" };
const INPUT = { recipientAgentCode: "AGT-000008", amount: 25_000 };

function makeTx(opts: { debitRows: unknown[]; creditRows?: unknown[] }) {
  const capture = { inserted: [] as any[], updateCalls: 0 };
  const tx = {
    select: vi.fn(() => ({
      from: () => ({ where: () => ({ limit: async () => [RECIPIENT] }) }),
    })),
    update: vi.fn(() => {
      capture.updateCalls++;
      const rows = capture.updateCalls === 1 ? opts.debitRows : (opts.creditRows ?? []);
      return { set: () => ({ where: () => ({ returning: async () => rows }) }) };
    }),
    insert: vi.fn(() => ({
      values: (v: any) => {
        capture.inserted.push(v);
        return Promise.resolve(undefined);
      },
    })),
  };
  return { tx, capture };
}

function makeDb(tx: any) {
  return {
    execute: vi.fn(async () => ({ rows: [] })),
    transaction: vi.fn(async (fn: any) => fn(tx)),
  };
}

beforeEach(() => {
  h.state.session = { ...SENDER };
});

describe("agentFloatTransfer.transfer", () => {
  it("happy path: sender debit + recipient credit + ledger row in ONE transaction", async () => {
    const { tx, capture } = makeTx({ debitRows: [{ id: 7 }], creditRows: [{ id: 8 }] });
    const db = makeDb(tx);
    h.state.db = db;
    const caller = agentFloatTransferRouter.createCaller(makeCtx("user"));

    const result: any = await caller.transfer(INPUT);

    expect(db.transaction).toHaveBeenCalledTimes(1);
    expect(tx.update).toHaveBeenCalledTimes(2); // debit then credit
    expect(tx.insert).toHaveBeenCalledTimes(1); // immutable ledger row
    expect(capture.inserted[0]).toMatchObject({
      agentId: SENDER.id,
      type: "Float Transfer",
      amount: "25000",
      status: "success",
    });
    expect(result).toMatchObject({
      amount: 25_000,
      recipientCode: RECIPIENT.agentCode,
      status: "completed",
    });
    expect(result.ref).toMatch(/^AFT-/);
  });

  it("guarded conditional debit returning 0 rows aborts: no credit, no ledger row", async () => {
    // Sender balance predicate fails atomically (concurrent drain) → 0 rows.
    const { tx, capture } = makeTx({ debitRows: [] });
    const db = makeDb(tx);
    h.state.db = db;
    const caller = agentFloatTransferRouter.createCaller(makeCtx("user"));

    await expect(caller.transfer(INPUT)).rejects.toMatchObject({
      code: "UNPROCESSABLE_CONTENT",
      message: expect.stringContaining("Insufficient float balance"),
    });
    expect(tx.update).toHaveBeenCalledTimes(1); // only the debit was attempted
    expect(tx.insert).not.toHaveBeenCalled();
    expect(capture.inserted).toHaveLength(0);
  });

  it("recipient disappearing mid-transaction (0 credit rows) also aborts", async () => {
    const { tx } = makeTx({ debitRows: [{ id: 7 }], creditRows: [] });
    const db = makeDb(tx);
    h.state.db = db;
    const caller = agentFloatTransferRouter.createCaller(makeCtx("user"));

    await expect(caller.transfer(INPUT)).rejects.toMatchObject({
      code: "NOT_FOUND",
    });
    expect(tx.insert).not.toHaveBeenCalled();
  });

  it("rejects transfers to self before opening a transaction", async () => {
    const { tx } = makeTx({ debitRows: [] });
    const db = makeDb(tx);
    h.state.db = db;
    const caller = agentFloatTransferRouter.createCaller(makeCtx("user"));

    await expect(
      caller.transfer({ recipientAgentCode: SENDER.agentCode, amount: 100 })
    ).rejects.toMatchObject({
      code: "BAD_REQUEST",
      message: expect.stringContaining("yourself"),
    });
    expect(db.transaction).not.toHaveBeenCalled();
  });

  it("idempotent replay returns the cached result without moving money", async () => {
    const idemHash = hashIdempotencyPayload({
      agentId: SENDER.id,
      recipientAgentCode: INPUT.recipientAgentCode,
      amount: INPUT.amount,
      narration: null,
    });
    const cached = {
      ref: "AFT-CACHED",
      amount: 25_000,
      recipientCode: RECIPIENT.agentCode,
      status: "completed",
      timestamp: new Date().toISOString(),
    };
    const { tx } = makeTx({ debitRows: [{ id: 7 }] });
    const db = makeDb(tx);
    db.execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] }) // claim INSERT lost
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: JSON.stringify({
              v: 1,
              requestHash: idemHash,
              status: "completed",
              result: cached,
            }),
            expires_at: new Date(Date.now() + 3600e3).toISOString(),
          },
        ],
      });
    h.state.db = db;
    const caller = agentFloatTransferRouter.createCaller(makeCtx("user"));

    const result = await caller.transfer({
      ...INPUT,
      idempotencyKey: "aft-idem-1",
    });

    expect(result).toEqual(cached);
    expect(db.transaction).not.toHaveBeenCalled();
  });

  it("same idempotency key with a different payload → 409 CONFLICT", async () => {
    const { tx } = makeTx({ debitRows: [{ id: 7 }] });
    const db = makeDb(tx);
    db.execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: JSON.stringify({
              v: 1,
              requestHash: "hash-of-a-different-payload",
              status: "completed",
              result: {},
            }),
            expires_at: new Date(Date.now() + 3600e3).toISOString(),
          },
        ],
      });
    h.state.db = db;
    const caller = agentFloatTransferRouter.createCaller(makeCtx("user"));

    await expect(
      caller.transfer({ ...INPUT, idempotencyKey: "aft-idem-1" })
    ).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("different request payload"),
    });
    expect(db.transaction).not.toHaveBeenCalled();
  });
});
