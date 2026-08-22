/**
 * Unit tests for server/lib/transactionHelper.ts — the claim-first,
 * payload-bound, fail-closed idempotency machinery that guards the money
 * paths, plus the withTransaction serialization-retry wrapper and the
 * amount / status-transition validators.
 *
 * DB layer is mocked at the module boundary (../../db) following the repo's
 * vitest.setup.ts convention; the module under test is the REAL
 * transactionHelper (real drizzle `sql` builder, no DB I/O).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { TRPCError } from "@trpc/server";

// ── Hoisted mock state ───────────────────────────────────────────────────────
const h = vi.hoisted(() => {
  const state: { db: any } = { db: null };
  return { state };
});

vi.mock("../../db", () => ({
  getDb: vi.fn(async () => h.state.db),
  writeAuditLog: vi.fn(async () => ({})),
  getAgentById: vi.fn(async () => null),
}));

vi.mock("../auditTrail", () => ({
  logAudit: vi.fn(() => ({})),
  queryAuditLog: vi.fn(() => ({ entries: [], total: 0 })),
  getAuditStats: vi.fn(() => ({})),
  exportAuditCsv: vi.fn(() => ""),
}));

import {
  claimIdempotencyKey,
  completeIdempotencyKey,
  failIdempotencyKey,
  hashIdempotencyPayload,
  withIdempotency,
  withIdempotencyTx,
  withTransaction,
  validateAmount,
  validateStatusTransition,
} from "../transactionHelper";

// ── Helpers ──────────────────────────────────────────────────────────────────
/** A completed-claim row as stored in idempotency_keys.response_data. */
function completedEnvelope(requestHash: string, result: unknown) {
  return JSON.stringify({ v: 1, requestHash, status: "completed", result });
}
function futureExpiry() {
  return new Date(Date.now() + 60 * 60 * 1000).toISOString();
}

beforeEach(() => {
  h.state.db = { execute: vi.fn(async () => ({ rows: [] })) };
});

describe("hashIdempotencyPayload", () => {
  it("is deterministic regardless of object key order", () => {
    const a = hashIdempotencyPayload({ amount: 100, agentId: 7, note: "x" });
    const b = hashIdempotencyPayload({ note: "x", agentId: 7, amount: 100 });
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });

  it("produces different hashes for different payloads", () => {
    expect(hashIdempotencyPayload({ amount: 100 })).not.toBe(
      hashIdempotencyPayload({ amount: 101 })
    );
  });
});

describe("claim-first idempotency (withIdempotency)", () => {
  it("claims the key first, runs the operation, and stores the result", async () => {
    const execute = vi
      .fn()
      // INSERT ... ON CONFLICT DO NOTHING RETURNING — claim won
      .mockResolvedValueOnce({ rows: [{ idempotency_key: "k1" }] })
      // UPDATE ... mark completed
      .mockResolvedValueOnce({ rows: [] });
    h.state.db = { execute };

    const fn = vi.fn(async () => ({ reference: "REF-1" }));
    const result = await withIdempotency("k1", fn, {
      payload: { amount: 100 },
    });

    expect(result).toEqual({ reference: "REF-1" });
    expect(fn).toHaveBeenCalledTimes(1);
    // exactly claim-INSERT then complete-UPDATE: the claim happens BEFORE fn
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it("replay: same key + same payload returns the cached result without re-running", async () => {
    const requestHash = hashIdempotencyPayload({ amount: 100 });
    const cached = { reference: "REF-CACHED", status: "success" };
    const execute = vi
      .fn()
      // INSERT claim lost — key already exists
      .mockResolvedValueOnce({ rows: [] })
      // SELECT existing claim
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: completedEnvelope(requestHash, cached),
            expires_at: futureExpiry(),
          },
        ],
      });
    h.state.db = { execute };

    const fn = vi.fn(async () => ({ reference: "REF-SHOULD-NOT-RUN" }));
    const result = await withIdempotency("k1", fn, {
      payload: { amount: 100 },
    });

    expect(result).toEqual(cached);
    expect(fn).not.toHaveBeenCalled();
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it("same key + different payload → 409 CONFLICT, operation never runs", async () => {
    const execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: completedEnvelope("a-different-hash", {}),
            expires_at: futureExpiry(),
          },
        ],
      });
    h.state.db = { execute };

    const fn = vi.fn(async () => ({}));
    await expect(
      withIdempotency("k1", fn, { payload: { amount: 999 } })
    ).rejects.toMatchObject({
      code: "CONFLICT",
      message: expect.stringContaining("different request payload"),
    });
    expect(fn).not.toHaveBeenCalled();
  });

  it("a pending (in-flight) claim → 409 CONFLICT", async () => {
    const requestHash = hashIdempotencyPayload(null);
    const execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: JSON.stringify({
              v: 1,
              requestHash,
              status: "pending",
            }),
            expires_at: futureExpiry(),
          },
        ],
      });
    h.state.db = { execute };

    await expect(withIdempotency("k1", async () => ({}))).rejects.toMatchObject(
      { code: "CONFLICT", message: expect.stringContaining("in progress") }
    );
  });

  it("a failed claim can be atomically re-claimed and retried", async () => {
    const requestHash = hashIdempotencyPayload(null);
    const execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] }) // INSERT lost
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: JSON.stringify({
              v: 1,
              requestHash,
              status: "failed",
              error: "boom",
            }),
            expires_at: futureExpiry(),
          },
        ],
      })
      .mockResolvedValueOnce({ rows: [{ idempotency_key: "k1" }] }) // CAS re-claim won
      .mockResolvedValueOnce({ rows: [] }); // complete
    h.state.db = { execute };

    const fn = vi.fn(async () => "retried-ok");
    await expect(withIdempotency("k1", fn)).resolves.toBe("retried-ok");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("legacy (pre-envelope) rows replay as completed claims", async () => {
    const execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [] })
      .mockResolvedValueOnce({
        rows: [
          {
            response_data: JSON.stringify({ reference: "LEGACY-1" }),
            expires_at: futureExpiry(),
          },
        ],
      });
    h.state.db = { execute };

    const fn = vi.fn(async () => ({}));
    await expect(withIdempotency("k1", fn)).resolves.toEqual({
      reference: "LEGACY-1",
    });
    expect(fn).not.toHaveBeenCalled();
  });

  it("fails closed when the DB is unavailable — never runs unprotected", async () => {
    h.state.db = null;
    const fn = vi.fn(async () => ({}));
    await expect(withIdempotency("k1", fn)).rejects.toThrow(
      /Database not available/
    );
    expect(fn).not.toHaveBeenCalled();
  });

  it("operation failure marks the claim failed so a retry may resume", async () => {
    const execute = vi
      .fn()
      .mockResolvedValueOnce({ rows: [{ idempotency_key: "k1" }] }) // claim won
      .mockResolvedValueOnce({ rows: [] }); // failIdempotencyKey UPDATE
    h.state.db = { execute };

    const fn = vi.fn(async () => {
      throw new Error("ledger exploded");
    });
    await expect(withIdempotency("k1", fn)).rejects.toThrow("ledger exploded");
    // claim INSERT + fail UPDATE
    expect(execute).toHaveBeenCalledTimes(2);
  });
});

describe("claimIdempotencyKey / completeIdempotencyKey direct contract", () => {
  it("returns { kind: 'claimed' } when the INSERT wins", async () => {
    h.state.db = {
      execute: vi.fn(async () => ({ rows: [{ idempotency_key: "k" }] })),
    };
    await expect(claimIdempotencyKey("k", "h")).resolves.toEqual({
      kind: "claimed",
    });
  });

  it("completeIdempotencyKey never throws, even on DB error", async () => {
    h.state.db = {
      execute: vi.fn(async () => {
        throw new Error("store down");
      }),
    };
    await expect(
      completeIdempotencyKey("k", "h", { ok: true })
    ).resolves.toBeUndefined();
  });

  it("failIdempotencyKey never throws, even on DB error", async () => {
    h.state.db = {
      execute: vi.fn(async () => {
        throw new Error("store down");
      }),
    };
    await expect(
      failIdempotencyKey("k", "h", "err")
    ).resolves.toBeUndefined();
  });

  it("throws TRPCError (not a generic error) on payload mismatch", async () => {
    h.state.db = {
      execute: vi
        .fn()
        .mockResolvedValueOnce({ rows: [] })
        .mockResolvedValueOnce({
          rows: [
            {
              response_data: completedEnvelope("other", null),
              expires_at: futureExpiry(),
            },
          ],
        }),
    };
    const err = await claimIdempotencyKey("k", "mine").catch(e => e);
    expect(err).toBeInstanceOf(TRPCError);
    expect(err.code).toBe("CONFLICT");
  });
});

describe("withIdempotencyTx (claim + operation in one transaction)", () => {
  it("replays a completed claim inside the transaction without running fn", async () => {
    const requestHash = hashIdempotencyPayload({ amount: 5 });
    const tx = {
      execute: vi
        .fn()
        .mockResolvedValueOnce({ rows: [] }) // INSERT lost
        .mockResolvedValueOnce({
          rows: [{ response_data: completedEnvelope(requestHash, "cached") }],
        }),
    };
    h.state.db = { transaction: vi.fn(async (fn: any) => fn(tx)) };

    const fn = vi.fn(async () => "fresh");
    await expect(
      withIdempotencyTx("k", { amount: 5 }, fn)
    ).resolves.toBe("cached");
    expect(fn).not.toHaveBeenCalled();
  });

  it("runs fn and finalizes the claim in the same transaction", async () => {
    const tx = {
      execute: vi
        .fn()
        .mockResolvedValueOnce({ rows: [{ idempotency_key: "k" }] }) // INSERT won
        .mockResolvedValueOnce({ rows: [] }), // final UPDATE
    };
    const transaction = vi.fn(async (fn: any) => fn(tx));
    h.state.db = { transaction };

    const fn = vi.fn(async () => "done");
    await expect(
      withIdempotencyTx("k", { amount: 5 }, fn)
    ).resolves.toBe("done");
    expect(transaction).toHaveBeenCalledTimes(1);
    expect(tx.execute).toHaveBeenCalledTimes(2);
  });
});

describe("withTransaction", () => {
  it("retries on serialization failure (40001) and succeeds", async () => {
    let calls = 0;
    h.state.db = {
      transaction: vi.fn(async (fn: any) => {
        calls++;
        if (calls === 1) {
          const err: any = new Error("serialization failure");
          err.code = "40001";
          throw err;
        }
        return fn({});
      }),
    };
    const fn = vi.fn(async () => "ok");
    await expect(withTransaction(fn, "t")).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1); // fn body only ran on the retry
    expect(h.state.db.transaction).toHaveBeenCalledTimes(2);
  });

  it("rethrows non-retryable errors immediately", async () => {
    h.state.db = {
      transaction: vi.fn(async () => {
        const err: any = new Error("unique violation");
        err.code = "23505";
        throw err;
      }),
    };
    await expect(withTransaction(async () => {}, "t")).rejects.toThrow(
      "unique violation"
    );
    expect(h.state.db.transaction).toHaveBeenCalledTimes(1);
  });

  it("throws when no database is available", async () => {
    h.state.db = null;
    await expect(withTransaction(async () => {}, "t")).rejects.toThrow(
      /Database not available/
    );
  });
});

describe("validateAmount", () => {
  it("accepts a normal positive amount", () => {
    expect(validateAmount(100)).toEqual({ valid: true });
  });
  it("rejects more than 2 decimal places", () => {
    expect(validateAmount(1.234).valid).toBe(false);
  });
  it("rejects non-positive and non-finite amounts", () => {
    expect(validateAmount(0).valid).toBe(false);
    expect(validateAmount(-5).valid).toBe(false);
    expect(validateAmount(Number.NaN).valid).toBe(false);
    expect(validateAmount(Number.POSITIVE_INFINITY).valid).toBe(false);
  });
  it("rejects amounts above the cap", () => {
    expect(validateAmount(100_000_001).valid).toBe(false);
  });
});

describe("validateStatusTransition", () => {
  const transitions = { pending: ["active", "rejected"], active: ["suspended"] };
  it("allows listed transitions", () => {
    expect(validateStatusTransition("pending", "active", transitions).valid).toBe(true);
  });
  it("rejects unlisted transitions", () => {
    const r = validateStatusTransition("pending", "suspended", transitions);
    expect(r.valid).toBe(false);
    expect(r.error).toContain("Cannot transition");
  });
  it("rejects unknown current status", () => {
    expect(validateStatusTransition("ghost", "active", transitions).valid).toBe(false);
  });
});
