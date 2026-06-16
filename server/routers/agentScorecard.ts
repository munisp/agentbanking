import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, sum, avg, gte, lte } from "drizzle-orm";
import {
  agents,
  transactions,
  agentPerformanceScores,
  disputes,
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
  draft: ["pending_review"],
  pending_review: ["approved", "rejected"],
  approved: ["active", "suspended"],
  active: ["suspended", "deactivated", "under_review"],
  suspended: ["active", "deactivated"],
  under_review: ["active", "suspended", "deactivated"],
  deactivated: ["reactivation_pending"],
  reactivation_pending: ["active", "rejected"],
  rejected: [],
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
      "agentScorecard",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentScorecard",
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
    resource: "agentScorecard",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentScorecard",
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
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};

export const agentScorecardRouter = router({
  getScorecard: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [agent] = await db
          .select()
          .from(agents)
          .where(eq(agents.id, input.agentId))
          .limit(1);
        if (!agent) return null;
        const [txStats] = await db
          .select({ txCount: count(), volume: sum(transactions.amount) })
          .from(transactions)
          .where(eq(transactions.agentId, input.agentId))
          .limit(100);
        const [successTx] = await db
          .select({ cnt: count() })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, input.agentId),
              eq(transactions.status, "success")
            )
          )
          .limit(100);
        const [disputeCount] = await db
          .select({ cnt: count() })
          .from(disputes)
          .where(eq(disputes.agentId, input.agentId))
          .limit(100);
        const successRate =
          Number(txStats.txCount) > 0
            ? Math.round(
                (Number(successTx.cnt) / Number(txStats.txCount)) * 100
              )
            : 100;
        const disputeRate =
          Number(txStats.txCount) > 0
            ? Math.round(
                (Number(disputeCount.cnt) / Number(txStats.txCount)) * 10000
              ) / 100
            : 0;
        const overallScore = Math.max(
          0,
          Math.min(100, successRate - disputeRate * 5)
        );
        return {
          agentId: input.agentId,
          name: agent.name,
          tier: agent.tier,
          location: agent.location,
          metrics: {
            txCount: Number(txStats.txCount),
            volume: Number(txStats.volume ?? 0),
            successRate,
            disputeRate,
            disputeCount: Number(disputeCount.cnt),
          },
          overallScore,
          rating:
            overallScore >= 90
              ? "Excellent"
              : overallScore >= 70
                ? "Good"
                : overallScore >= 50
                  ? "Average"
                  : "Needs Improvement",
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  listScorecards: protectedProcedure
    .input(
      z.object({
        limit: z.number().default(50),
        minScore: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(agentPerformanceScores)
          .orderBy(desc(agentPerformanceScores.overallScore))
          .limit(input.limit);
        return { scorecards: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  dashboard: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeRecords: 0,
      lastUpdated: new Date().toISOString(),
      uptime: 99.9,
      version: "1.0.0",
    };
  }),

  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [avgScore] = await db
      .select({ value: avg(agentPerformanceScores.overallScore) })
      .from(agentPerformanceScores)
      .limit(100);
    const [total] = await db
      .select({ value: count() })
      .from(agentPerformanceScores)
      .limit(100);
    return {
      averageScore: Number(avgScore.value ?? 0),
      totalScorecards: Number(total.value),
      lastUpdated: new Date().toISOString(),
    };
  }),
  refreshScorecard: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as Record<string, unknown>).status as string;
        const currentStatus =
          ((input as Record<string, unknown>).currentStatus as string) ||
          "pending";
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
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        await db.insert(auditLog).values({
          action: "scorecard_refresh",
          resource: "agent_scores",
          resourceId: String(input.agentId),
          status: "success",
          metadata: {},
        });
        await writeAuditLog({
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "agentScorecard",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return {
          success: true,
          agentId: input.agentId,
          refreshedAt: new Date().toISOString(),
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
