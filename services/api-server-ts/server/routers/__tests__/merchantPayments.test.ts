/**
 * merchantPayments.processPayment — funds-flow unit tests.
 *
 * Covers NF-FF-1 behavior in server/routers/merchantPayments.ts:
 *  - insufficient float → debit guard rejects before any money movement
 *  - happy path produces the guarded debit, merchant credit, and fee/commission
 *    legs inside ONE database transaction (withTransaction wrapper)
 *  - claim-first idempotency: replay returns the cached result; a reused key
 *    with a different payload → 409 CONFLICT
 *
 * The DB (../../db), agent session, middleware mesh, drizzle operators and the
 * drizzle schema are mocked at the module boundary; the router and
 * lib/transactionHelper execute for real.
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

vi.mock("../../kafkaClient", () => ({ publishEvent: vi.fn(async () => {}) }));
vi.mock("../../redisClient", () => ({
  cacheSet: vi.fn(async () => {}),
  cacheGet: vi.fn(async () => null),
}));
vi.mock("../../tbClient", () => ({ tbCreateTransfer: vi.fn(async () => ({})) }));
vi.mock("../../fluvio", () => ({ fluvioProduce: vi.fn(async () => ({})) }));
vi.mock("../../lakehouse", () => ({ ingestToLakehouse: vi.fn(async () => ({})) }));
vi.mock("../../lib/auditTrail", () => ({ logAudit: vi.fn(() => ({})) }));

vi.mock("drizzle-orm", async () => {
  const { drizzleOrmStub } = await import("./fundsFlowTestKit");
  return drizzleOrmStub();
});
vi.mock("../../../drizzle/schema", async () => {
  const { drizzleSchemaStub } = await import("./fundsFlowTestKit");
  return drizzleSchemaStub();
});

import { merchantPaymentsRouter } from "../merchantPayments";
import { hashIdempotencyPayload } from "../../lib/transactionHelper";
import { makeCtx, selectChain } from "./fundsFlowTestKit";

const AGENT_SESSION = {
  id: 7,
  agentCode: "AGT-000007",
  name: "Test Agent",
  tier: "1",
  role: "agent",
};
const MERCHANT = {
  id: 11,
  merchantCode: "MCH-001",
  businessName: "Test Mart",
  status: "active",
};
const INPUT = { merchantCode: "MCH-001", amount: 10_000 };

/**
 * db.select() with no column projection → merchant lookup;
 * db.select({ floatBalance }) → agent float advisory check.
 */
function makeDbWithFloat(floatBalance: string) {
  return {
    execute: vi.fn(async () => ({ rows: [] })),
    transaction: vi.fn(),
    select: vi.fn((fields?: unknown) =>
      selectChain(fields ? [{ floatBalance }] : [MERCHANT])
    ),
  };
}

function makeTx(debitRows: unknown[]) {
  const capture = { insertedValues: [] as any[], updateCount: 0 };
  const tx = {
    execute: vi.fn(async () => ({ rows: debitRows })),
    update: vi.fn(() => {
      capture.updateCount++;
      return { set: () => ({ where: vi.fn(async () => undefined) }) };
    }),
    insert: vi.fn(() => ({
      values: (v: any) => {
        capture.insertedValues.push(v);
        return { returning: async () => [{ id: 999 }] };
      },
    })),
  };
  return { tx, capture };
}

beforeEach(() => {
  h.state.session = { ...AGENT_SESSION };
});

describe("merchantPayments.processPayment", () => {
  it("insufficient float → BAD_REQUEST and no transaction is ever opened", async () => {
    const db = makeDbWithFloat("100"); // float 100 < amount 10_000
    h.state.db = db;
    const caller = merchantPaymentsRouter.createCaller(makeCtx("user"));

    await expect(caller.processPayment(INPUT)).rejects.toMatchObject({
      code: "BAD_REQUEST",
      message: expect.stringContaining("Insufficient float"),
    });
    expect(db.transaction).not.toHaveBeenCalled();
  });

  it("happy path: guarded debit + merchant credit + fee legs in ONE transaction", async () => {
    const db = makeDbWithFloat("100000");
    const { tx, capture } = makeTx([{ id: AGENT_SESSION.id }]);
    db.transaction = vi.fn(async (fn: any) => fn(tx));
    h.state.db = db;
    const caller = merchantPaymentsRouter.createCaller(makeCtx("user"));

    const result: any = await caller.processPayment(INPUT);

    // Exactly one transaction wrapper around all three legs.
    expect(db.transaction).toHaveBeenCalledTimes(1);
    // Leg 1: guarded conditional debit of the agent float.
    expect(tx.execute).toHaveBeenCalledTimes(1);
    // Leg 2: merchant wallet credit (net of fee) inside the same tx.
    expect(tx.update).toHaveBeenCalledTimes(1);
    // Leg 3: ledger row with fee + commission recorded.
    expect(tx.insert).toHaveBeenCalledTimes(1);

    const inserted = capture.insertedValues[0];
    expect(inserted.agentId).toBe(AGENT_SESSION.id);
    expect(inserted.amount).toBe("10000");
    expect(inserted.fee).toBe("150"); // merchantFee = round(10000 * 0.015)
    expect(inserted.commission).toBe("100"); // agentCommission = round(10000 * 0.01)
    expect(inserted.metadata.platformFeeLeg).toMatchObject({
      type: "platform_revenue",
      amount: 150,
      agentFloatDebited: "10000",
      merchantCredited: "9850",
    });

    expect(result).toMatchObject({
      merchantName: "Test Mart",
      amount: 10_000,
      merchantFee: 150,
      agentCommission: 100,
      status: "success",
      transactionId: 999,
    });
    expect(result.ref).toMatch(/^MPY-/);
  });

  it("guarded debit returning 0 rows → UNPROCESSABLE_CONTENT, no credit/insert", async () => {
    const db = makeDbWithFloat("100000"); // advisory check passes…
    const { tx, capture } = makeTx([]); // …but the atomic guard loses the race
    db.transaction = vi.fn(async (fn: any) => fn(tx));
    h.state.db = db;
    const caller = merchantPaymentsRouter.createCaller(makeCtx("user"));

    await expect(caller.processPayment(INPUT)).rejects.toMatchObject({
      code: "UNPROCESSABLE_CONTENT",
      message: expect.stringContaining("Insufficient agent float"),
    });
    expect(tx.update).not.toHaveBeenCalled();
    expect(tx.insert).not.toHaveBeenCalled();
    expect(capture.insertedValues).toHaveLength(0);
  });

  it("idempotent replay: same key + same payload returns the cached result", async () => {
    const idemHash = hashIdempotencyPayload({
      agentId: AGENT_SESSION.id,
      merchantCode: INPUT.merchantCode,
      amount: INPUT.amount,
      customerPhone: null,
    });
    const cached = {
      ref: "MPY-CACHED",
      merchantName: "Test Mart",
      amount: 10_000,
      merchantFee: 150,
      agentCommission: 100,
      status: "success",
      transactionId: 555,
    };
    const db = makeDbWithFloat("100000");
    db.execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] }) // claim INSERT lost — key exists
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
    db.transaction = vi.fn();
    h.state.db = db;
    const caller = merchantPaymentsRouter.createCaller(makeCtx("user"));

    const result = await caller.processPayment({
      ...INPUT,
      idempotencyKey: "mpy-idem-1",
    });

    expect(result).toEqual(cached);
    // No money movement at all on replay.
    expect(db.transaction).not.toHaveBeenCalled();
    expect(db.select).not.toHaveBeenCalled();
    expect(db.execute).toHaveBeenCalledTimes(2);
  });

  it("same idempotency key with a different payload → 409 CONFLICT", async () => {
    const db = makeDbWithFloat("100000");
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
    db.transaction = vi.fn();
    h.state.db = db;
    const caller = merchantPaymentsRouter.createCaller(makeCtx("user"));

    await expect(
      caller.processPayment({ ...INPUT, idempotencyKey: "mpy-idem-1" })
    ).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("different request payload"),
    });
    expect(db.transaction).not.toHaveBeenCalled();
  });

  it("no agent session → UNAUTHORIZED", async () => {
    h.state.session = null;
    h.state.db = makeDbWithFloat("100000");
    const caller = merchantPaymentsRouter.createCaller(makeCtx("user"));
    await expect(caller.processPayment(INPUT)).rejects.toMatchObject({
      code: "UNAUTHORIZED",
    });
  });
});
