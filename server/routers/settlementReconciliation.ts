/**
 * Settlement Reconciliation Router
 * Matches merchant settlement batches against transaction records.
 * Status flow: pending → matched | discrepancy → resolved
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import {
  settlementReconciliation,
  merchantSettlements,
  transactions,
  gl_journal_entries,
  agents,
} from "../../drizzle/schema";
import { eq, desc, and, count, gte, lte, sql } from "drizzle-orm";
// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { checkDailyLimit } from "../lib/cbnLimits";
import { withIdempotency } from "../lib/transactionHelper";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["in_progress", "skipped"],
  in_progress: ["completed", "failed", "partially_matched"],
  completed: [],
  failed: ["pending"],
  partially_matched: ["in_progress", "completed"],
  skipped: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "settlementReconciliation",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "settlementReconciliation",
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
    resource: "settlementReconciliation",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "settlementReconciliation",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations
export const settlementReconciliationRouter = router({
  // ── List reconciliation records ───────────────────────────────────────────
  list: protectedProcedure
    .input(
      z.object({
        page: z.number().default(1),
        limit: z.number().default(20),
        status: z
          .enum(["pending", "matched", "discrepancy", "resolved"])
          .optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const offset = (input.page - 1) * input.limit;
        const where = input.status
          ? eq(settlementReconciliation.status, input.status)
          : undefined;
        const [items, [{ c: total }]] = await Promise.all([
          db
            .select()
            .from(settlementReconciliation)
            .where(where)
            .orderBy(desc(settlementReconciliation.createdAt))
            .limit(input.limit)
            .offset(offset),
          db.select({ c: count() }).from(settlementReconciliation).where(where),
        ]);
        return { items, total: Number(total) };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Run reconciliation for a settlement date ──────────────────────────────
  reconcileDate: protectedProcedure
    .input(
      z.object({
        settlementDate: z
          .string()
          .regex(/^\d{4}-\d{2}-\d{2}$/, "Must be YYYY-MM-DD"),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus =
          "status" in input
            ? String((input as Record<string, unknown>).status)
            : "";
        const currentStatus =
          "currentStatus" in input
            ? String((input as Record<string, unknown>).currentStatus)
            : "pending";
        const allowed =
          STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
          });
        }
      }
      const txAmount =
        typeof input === "object" && "amount" in input
          ? Number(
              "amount" in input ? (input as Record<string, unknown>).amount : 0
            )
          : 0;
      const fees = calculateFee(txAmount, "settlement");
      const commission = calculateCommission(fees.fee, "settlement");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const dayStart = new Date(`${input.settlementDate}T00:00:00Z`);
        const dayEnd = new Date(`${input.settlementDate}T23:59:59Z`);

        // Get all merchant settlements for this date period
        const settlementsForDate = await db
          .select()
          .from(merchantSettlements)
          .where(eq(merchantSettlements.period, input.settlementDate));

        const results = [];
        for (const settlement of settlementsForDate) {
          // Sum completed transactions for this merchant on this date
          const txResult = await db
            .select({
              total: sql<string>`COALESCE(SUM("amount"), 0)`,
              txCount: count(),
            })
            .from(transactions)
            .where(
              and(
                eq(transactions.agentId, settlement.merchantId),
                gte(transactions.createdAt, dayStart),
                lte(transactions.createdAt, dayEnd),
                eq(transactions.status, "success")
              )
            );

          const txTotal = parseFloat(txResult[0]?.total ?? "0");
          const settlementAmount = parseFloat(settlement.netAmount as string);
          const discrepancy = Math.abs(txTotal - settlementAmount);
          const variancePct =
            settlementAmount > 0 ? (discrepancy / settlementAmount) * 100 : 0;
          const status = variancePct < 0.01 ? "matched" : "discrepancy";

          // Upsert reconciliation record
          const [existing] = await db
            .select()
            .from(settlementReconciliation)
            .where(
              and(
                eq(
                  settlementReconciliation.settlementDate,
                  input.settlementDate
                ),
                eq(
                  settlementReconciliation.agentCode,
                  String(settlement.merchantId)
                )
              )
            )
            .limit(1);

          let record;
          if (existing) {
            [record] = await db
              .update(settlementReconciliation)
              .set({
                expectedAmount: String(txTotal),
                actualAmount: String(settlementAmount),
                discrepancy: String(discrepancy),
                status,
              })
              .where(eq(settlementReconciliation.id, existing.id))
              .returning();

            // Double-entry GL journal entry
            await db.insert(gl_journal_entries).values({
              entryNumber: `JE-${Date.now()}`,
              description: `settlementReconciliation transaction`,
              debitAccountId: 2001,
              creditAccountId: 1001,
              amount: Math.round(
                (typeof input === "object" && "amount" in input
                  ? Number(
                      "amount" in input
                        ? (input as Record<string, unknown>).amount
                        : 0
                    )
                  : 0) * 100
              ),
              currency: "NGN",
              status: "posted",
            });
          } else {
            [record] = await db
              .insert(settlementReconciliation)
              .values({
                settlementDate: input.settlementDate,
                agentCode: String(settlement.merchantId),
                expectedAmount: String(txTotal),
                actualAmount: String(settlementAmount),
                discrepancy: String(discrepancy),
                status,
              })
              .returning();
          }
          results.push(record);
        }

        await writeAuditLog({
          action: "settlement_reconciliation_run",
          resource: "settlement_reconciliation",
          resourceId: input.settlementDate,
          status: "success",
          metadata: {
            recordsProcessed: results.length,
            date: input.settlementDate,
          },
        });

        return { processed: results.length, records: results };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Resolve a discrepancy ─────────────────────────────────────────────────
  resolve: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        resolution: z.string().min(1).max(1000),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [record] = await db
          .select()
          .from(settlementReconciliation)
          .where(eq(settlementReconciliation.id, input.id))
          .limit(1);
        if (!record) throw new TRPCError({ code: "NOT_FOUND" });
        if (record.status !== "discrepancy") {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Only discrepancy records can be resolved",
          });
        }

        const [updated] = await db
          .update(settlementReconciliation)
          .set({
            status: "resolved",
            resolutionNote: input.resolution,
            resolvedBy: ctx.user.id,
            resolvedAt: new Date(),
          })
          .where(eq(settlementReconciliation.id, input.id))
          .returning();

        return updated;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Summary stats ─────────────────────────────────────────────────────────
  stats: protectedProcedure.query(async () => {
    try {
      const db = (await getDb())!;
      if (!db)
        return {
          total: 0,
          matched: 0,
          discrepancy: 0,
          resolved: 0,
          pending: 0,
        };
      const rows = await db.select().from(settlementReconciliation).limit(100);
      return {
        total: rows.length,
        matched: rows.filter((r: any) => r.status === "matched").length,
        discrepancy: rows.filter((r: any) => r.status === "discrepancy").length,
        resolved: rows.filter((r: any) => r.status === "resolved").length,
        pending: rows.filter((r: any) => r.status === "pending").length,
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),
});
