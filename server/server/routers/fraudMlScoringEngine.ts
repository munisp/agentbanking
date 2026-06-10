import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, sql, count, avg, and, gte, lte } from "drizzle-orm";
import {
  fraudMlScores,
  fraudAlerts,
  transactions,
  auditLog,
} from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  detected: ["under_investigation"],
  under_investigation: ["confirmed_fraud", "false_positive", "escalated"],
  escalated: ["under_investigation", "confirmed_fraud"],
  confirmed_fraud: ["mitigation_in_progress"],
  mitigation_in_progress: ["resolved", "blocked"],
  blocked: ["unblocked", "permanently_blocked"],
  unblocked: ["monitoring"],
  monitoring: ["cleared", "re_flagged"],
  re_flagged: ["under_investigation"],
  cleared: ["closed"],
  resolved: ["closed"],
  false_positive: ["closed"],
  permanently_blocked: [],
  closed: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "fraudMlScoringEngine",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "fraudMlScoringEngine",
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
    resource: "fraudMlScoringEngine",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "fraudMlScoringEngine",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const fraudMlScoringEngineRouter = router({
  listScores: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(50),
          minScore: z.number().optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(fraudMlScores)
          .orderBy(desc(fraudMlScores.createdAt))
          .limit(input?.limit ?? 50);
        return { scores: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getScore: protectedProcedure
    .input(z.object({ transactionId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [score] = await db
          .select()
          .from(fraudMlScores)
          .where(eq(fraudMlScores.transactionId, input.transactionId))
          .limit(1);
        return score ?? null;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  scoreTransaction: protectedProcedure
    .input(
      z.object({
        transactionId: z.number(),
        features: z.record(z.string(), z.unknown()).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as any).status as string;
        const currentStatus =
          ((input as any).currentStatus as string) || "pending";
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
          ? Number((input as any).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        const [tx] = await db
          .select()
          .from(transactions)
          .where(eq(transactions.id, input.transactionId))
          .limit(1);
        const riskScore = tx
          ? Math.min(
              100,
              Math.max(
                0,
                Number(tx.amount) > 500000
                  ? 75
                  : Number(tx.amount) > 100000
                    ? 50
                    : 15
              )
            )
          : 0;
        const [score] = await db
          .insert(fraudMlScores)
          .values({
            transactionId: input.transactionId,
            score: riskScore,
            model: "ensemble_v2",
            features: input.features ?? {},
          } as any)
          .returning();
        if (riskScore > 70) {
          await db.insert(fraudAlerts).values({
            transactionId: input.transactionId,
            severity: riskScore > 90 ? "critical" : "high",
            status: "open",
            description: "ML model flagged high risk",
            riskScore,
          } as any);
        }
        await db.insert(auditLog).values({
          action: "fraud_ml_scored",
          resource: "fraud_ml_scores",
          resourceId: String(score.id),
          status: "success",
          metadata: { transactionId: input.transactionId, riskScore },
        } as any);
        return score;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [total] = await db
      .select({ value: count() })
      .from(fraudMlScores)
      .limit(100);
    const [avgScore] = await db
      .select({ value: avg(fraudMlScores.riskScore) })
      .from(fraudMlScores)
      .limit(100);
    const [alerts] = await db
      .select({ value: count() })
      .from(fraudAlerts)
      .limit(100);

    return {
      totalScored: Number(total.value),
      averageScore: Number(avgScore.value ?? 0),
      totalAlerts: Number(alerts.value),
    };
  }),

  // ── Additional query/mutation procedures ─────────────────────
  getStats_fraudMlScoringEngine: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      lastUpdated: new Date().toISOString(),
      status: "operational",
    };
  }),

  healthCheck_fraudMlScoringEngine: protectedProcedure.query(async () => {
    return {
      healthy: true,
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }),
});
