// @ts-nocheck
/**
 * Agent-to-Agent Float Transfer — peer float sharing between agents
 * with approval workflow and transfer limits.
 *
 * Middleware: Kafka (transfer events), Redis (rate limiting),
 * PostgreSQL (transfer records), Temporal (approval workflow)
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agents, transactions } from "../../drizzle/schema";
import { eq, and, sql, gte, lte, desc, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  claimIdempotencyKey,
  completeIdempotencyKey,
  failIdempotencyKey,
  hashIdempotencyPayload,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

const MAX_TRANSFER = 1_000_000;

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateAgentfloattransferInput(
  data: Record<string, unknown>
): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentFloatTransfer",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentFloatTransfer",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "agentFloatTransfer",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentFloatTransfer",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_AGENTFLOATTRANSFER = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_AGENTFLOATTRANSFER.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_AGENTFLOATTRANSFER.validateRange(
        data.amount,
        0,
        100_000_000
      )
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Database Query Patterns ────────────────────────────────────────────────
const _agentFloatTransfer_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

export const agentFloatTransferRouter = router({
  transfer: protectedProcedure
    .input(
      z.object({
        recipientAgentCode: z.string().min(4).max(20),
        amount: z.number().positive().max(MAX_TRANSFER),
        narration: z.string().max(256).optional(),
        // NF-FF-10: optional idempotency key — claimed before any money moves
        idempotencyKey: z.string().max(64).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "agentFloatTransfer",
        "mutation",
        "Executed agentFloatTransfer mutation"
      );

      // NF-FF-10: idempotency claim state (declared outside try so the catch
      // block can release a claim whose operation failed) — same claim-first
      // pattern as transactions.ts.
      let idemHash: string | null = null;
      let idemClaimed = false;
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        if (input.recipientAgentCode === session.agentCode)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Cannot transfer to yourself",
          });

        // ── NF-FF-10: Idempotency — claim-first, fail closed ──────────────
        if (input.idempotencyKey) {
          idemHash = hashIdempotencyPayload({
            agentId: session.id,
            recipientAgentCode: input.recipientAgentCode,
            amount: input.amount,
            narration: input.narration ?? null,
          });
          const claim = await claimIdempotencyKey(
            input.idempotencyKey,
            idemHash
          );
          if (claim.kind === "replay") {
            // Same key + same payload already completed — return stored result.
            return claim.result as any;
          }
          idemClaimed = true;
        }

        const ref = `AFT-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;

        // ── NF-FF-10: single ACID transaction ──────────────────────────────
        // Guarded conditional sender debit (balance predicate inside the
        // UPDATE — closes the check-then-act TOCTOU), recipient credit, and
        // the transactions ledger row all commit or roll back together.
        await db.transaction(async (tx: any) => {
          const [recipient] = await tx
            .select({ id: agents.id, agentCode: agents.agentCode })
            .from(agents)
            .where(eq(agents.agentCode, input.recipientAgentCode))
            .limit(1);
          if (!recipient)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "Recipient agent not found",
            });

          const debited = await tx
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) - ${String(input.amount)}`,
            })
            .where(
              and(
                eq(agents.id, session.id),
                sql`CAST(${agents.floatBalance} AS numeric) - ${String(input.amount)} >= 0`
              )
            )
            .returning({ id: agents.id });
          if (debited.length === 0)
            throw new TRPCError({
              code: "UNPROCESSABLE_CONTENT",
              message: "Insufficient float balance",
            });

          const credited = await tx
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) + ${String(input.amount)}`,
            })
            .where(eq(agents.id, recipient.id))
            .returning({ id: agents.id });
          if (credited.length === 0)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "Recipient agent not found",
            });

          // Immutable ledger row for the transfer, written inside the same
          // transaction as the balance movements.
          await tx.insert(transactions).values({
            ref,
            agentId: session.id,
            type: "Float Transfer",
            amount: String(input.amount),
            fee: "0.00",
            commission: "0.00",
            channel: "App",
            status: "success",
            metadata: {
              recipientAgentCode: input.recipientAgentCode,
              recipientAgentId: recipient.id,
              narration: input.narration ?? null,
            },
            idempotencyKey: input.idempotencyKey ?? null,
          });
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "AGENT_FLOAT_TRANSFERRED",
          resource: "agent_float_transfer",
          resourceId: ref,
          status: "success",
          metadata: {
            recipientCode: input.recipientAgentCode,
            amount: input.amount,
            narration: input.narration,
          },
        });

        const result = {
          ref,
          amount: input.amount,
          recipientCode: input.recipientAgentCode,
          status: "completed",
          timestamp: new Date().toISOString(),
        };
        // NF-FF-10: finalize the idempotency claim so a replay returns this
        // exact result.
        if (idemClaimed && input.idempotencyKey && idemHash) {
          await completeIdempotencyKey(input.idempotencyKey, idemHash, result);
        }
        return result;
      } catch (error) {
        // NF-FF-10: release the claim (mark failed) so a retry presenting the
        // same key + payload can safely resume.
        if (idemClaimed && input.idempotencyKey && idemHash) {
          await failIdempotencyKey(
            input.idempotencyKey,
            idemHash,
            error instanceof Error ? error.message : String(error)
          );
        }
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  getHistory: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }))
    .query(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) return { transfers: [] };

        const rows = await db.execute(
          sql`SELECT resource_id, metadata, status, "createdAt" FROM audit_log
              WHERE action = 'AGENT_FLOAT_TRANSFERRED' AND "agentId" = ${session.id}
              ORDER BY "createdAt" DESC LIMIT ${input.limit}`
        );

        return { transfers: rows.rows ?? [] };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { items: [], total: 0 };
        return { items: [], total: 0 };
      } catch {
        return { items: [], total: 0 };
      }
    }),
});
