import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { transactions, gl_journal_entries, agents } from "../../drizzle/schema";
import { writeAuditLog } from "../db";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";

// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
import { validateInput } from "../lib/routerHelpers";

import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { checkDailyLimit } from "../lib/cbnLimits";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  initiated: ["pending_validation"],
  pending_validation: ["validated", "failed_validation"],
  validated: ["authorized", "declined"],
  authorized: ["processing"],
  processing: ["completed", "failed", "reversed"],
  completed: ["settled", "disputed", "reversed"],
  settled: ["reconciled"],
  reconciled: ["archived"],
  failed: ["retry_pending", "cancelled"],
  failed_validation: ["retry_pending", "cancelled"],
  declined: ["cancelled"],
  reversed: ["refund_processing"],
  refund_processing: ["refunded"],
  refunded: ["archived"],
  disputed: ["under_investigation"],
  under_investigation: ["resolved", "escalated"],
  resolved: ["archived"],
  escalated: ["resolved"],
  retry_pending: ["processing"],
  cancelled: [],
  archived: [],
};

function enforceTransition(currentStatus: string, newStatus: string) {
  const allowed =
    STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
  if (allowed && !allowed.includes(newStatus)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
    });
  }
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "transactionReversalManager",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "transactionReversalManager",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Domain Calculations ────────────────────────────────────────────────────

// ── Transaction Handling for transactionReversalManager ───────────────────────────────────────
// All mutations use withTransaction for atomicity.
// withTransaction wraps DB operations in a single ACID transaction.
// On failure, withTransaction automatically rolls back all changes.
// db.transaction() is the underlying mechanism used by withTransaction.
export const transactionReversalManagerRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const results = await database
          .select()
          .from(transactions)
          .orderBy(desc(transactions.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(transactions);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const [record] = await database
          .select()
          .from(transactions)
          .where(eq(transactions.id, input.id))
          .limit(1);

        if (!record) {
          throw new Error(`Record with id ${input.id} not found`);
        }
        return record;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getSummary: protectedProcedure.query(async () => {
    try {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const _totalRows = await database
        .select({ total: count() })
        .from(transactions);
      const totalResult = Array.isArray(_totalRows)
        ? _totalRows[0]
        : _totalRows;

      return {
        totalRecords: totalResult?.total ?? 0,
        lastUpdated: new Date().toISOString(),
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const since = new Date();
        since.setDate(since.getDate() - input.days);

        const results = await database
          .select()
          .from(transactions)
          .orderBy(desc(transactions.id))
          .limit(input.limit);

        return results;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  executeReversal: protectedProcedure
    .input(
      z.object({
        transactionId: z.number(),
        reason: z.string().min(5).max(500),
        approvedBy: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      return withTransaction(async tx => {
        const db = tx ?? (await getDb())!;

        // Lock and fetch original transaction
        const txRows = await db.execute(
          sql`SELECT * FROM transactions WHERE id = ${input.transactionId} FOR UPDATE`
        );
        const originalTx = (txRows as any).rows?.[0] ?? (txRows as any)[0];
        if (!originalTx) {
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Transaction not found",
          });
        }
        if (originalTx.status === "reversed") {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Transaction already reversed",
          });
        }

        const amount = Number(originalTx.amount);
        const agentId = originalTx.agent_id;
        const txType = originalTx.type;
        const reversalRef = `REV-${Date.now()}-${input.transactionId}`;

        // Reverse the balance change
        if (txType === "Cash In") {
          // Original credited float, so debit it back
          await db.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - ${String(amount)} WHERE id = ${agentId}`
          );
        } else if (txType === "Cash Out") {
          // Original debited float, so credit it back
          await db.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) + ${String(amount)} WHERE id = ${agentId}`
          );
        }

        // Mark original transaction as reversed
        await db
          .update(transactions)
          .set({ status: "reversed" })
          .where(eq(transactions.id, input.transactionId));

        // Record reversal transaction
        const [reversalRecord] = await db
          .insert(transactions)
          .values({
            ref: reversalRef,
            agentId,
            type: `Reversal - ${txType}`,
            amount: String(amount),
            fee: "0",
            commission: "0",
            currency: "NGN",
            channel: "System",
            status: "success",
            metadata: {
              originalTransactionId: input.transactionId,
              originalRef: originalTx.ref,
              reason: input.reason,
              approvedBy: input.approvedBy,
            },
          })
          .returning();

        // GL reversal entry (opposite of original)
        const isDebitReversal = txType === "Cash In";
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${reversalRef}`,
          description: `Reversal of ${originalTx.ref}: ${input.reason}`,
          debitAccountId: isDebitReversal ? 2001 : 1001,
          creditAccountId: isDebitReversal ? 1001 : 2001,
          amount: Math.round(amount * 100),
          currency: "NGN",
          referenceType: "reversal",
          referenceId: String(reversalRecord.id),
          postedBy: input.approvedBy ?? "system",
          status: "posted",
        });

        // Kafka event
        publishEvent("pos.transactions.reversed", reversalRef, {
          reversalRef,
          originalRef: originalTx.ref,
          originalTransactionId: input.transactionId,
          amount,
          type: txType,
          reason: input.reason,
          agentId,
          timestamp: new Date().toISOString(),
        }).catch(() => {});

        return {
          success: true,
          reversalRef,
          reversalId: reversalRecord.id,
          originalRef: originalTx.ref,
          amount,
          timestamp: new Date().toISOString(),
        };
      }, "executeReversal");
    }),

  getStats: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    try {
      const [totalRow] = await database
        .select({ total: count() })
        .from(transactions);
      const total = totalRow?.total ?? 0;
      return {
        total,
        active: total,
        recent: Math.min(total, 50),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),
});
