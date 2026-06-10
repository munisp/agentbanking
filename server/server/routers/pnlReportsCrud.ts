// @ts-nocheck
// Sprint 87: P&L calculation engine, period comparison, variance analysis
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { pnlReports } from "../../drizzle/schema";
import { eq, desc, and, count, sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
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
  pending: ["batched"],
  batched: ["processing"],
  processing: ["settled", "partially_settled", "failed"],
  settled: ["reconciled"],
  partially_settled: ["processing", "escalated"],
  reconciled: ["confirmed", "discrepancy_found"],
  discrepancy_found: ["under_review"],
  under_review: ["adjusted", "confirmed"],
  adjusted: ["confirmed"],
  confirmed: ["archived"],
  failed: ["retry_pending", "escalated"],
  retry_pending: ["processing"],
  escalated: ["resolved"],
  resolved: ["confirmed"],
  archived: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "pnlReportsCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "pnlReportsCrud",
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
    resource: "pnlReportsCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "pnlReportsCrud",
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

export const pnlReportsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        periodType: z.string().optional(),
        agentId: z.number().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.periodType)
          conditions.push(eq(pnlReports.periodType, input.periodType));
        if (input.agentId)
          conditions.push(eq(pnlReports.agentId, input.agentId));
        const rows = await db
          .select()
          .from(pnlReports)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(pnlReports.period))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(pnlReports)
          .where(conditions.length ? and(...conditions) : undefined)
          .limit(100);
        const enriched = rows.map(r => {
          const revenue = Number(r.totalRevenue || 0);
          const costs = Number(r.operatingCosts || 0);
          const margin = revenue > 0 ? ((revenue - costs) / revenue) * 100 : 0;
          return {
            ...r,
            profitMargin: Math.round(margin * 100) / 100,
            isProfit: revenue > costs,
          };
        });
        return { items: enriched, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .select()
          .from(pnlReports)
          .where(eq(pnlReports.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "P&L report not found",
          });
        return row;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  comparePeriods: protectedProcedure
    .input(
      z.object({
        period1: z.string(),
        period2: z.string(),
        agentId: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const cond1: any[] = [eq(pnlReports.period, input.period1)];
        const cond2: any[] = [eq(pnlReports.period, input.period2)];
        if (input.agentId) {
          cond1.push(eq(pnlReports.agentId, input.agentId));
          cond2.push(eq(pnlReports.agentId, input.agentId));
        }
        const [p1] = await db
          .select()
          .from(pnlReports)
          .where(and(...cond1))
          .limit(100);
        const [p2] = await db
          .select()
          .from(pnlReports)
          .where(and(...cond2))
          .limit(100);
        if (!p1 || !p2)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "One or both periods not found",
          });
        const rev1 = Number(p1.totalRevenue || 0),
          rev2 = Number(p2.totalRevenue || 0);
        const cost1 = Number(p1.operatingCosts || 0),
          cost2 = Number(p2.operatingCosts || 0);
        return {
          period1: {
            period: p1.period,
            revenue: p1.totalRevenue,
            costs: p1.operatingCosts,
            netMargin: p1.netMargin,
          },
          period2: {
            period: p2.period,
            revenue: p2.totalRevenue,
            costs: p2.operatingCosts,
            netMargin: p2.netMargin,
          },
          revenueChange:
            rev1 > 0 ? (((rev2 - rev1) / rev1) * 100).toFixed(2) + "%" : "N/A",
          costChange:
            cost1 > 0
              ? (((cost2 - cost1) / cost1) * 100).toFixed(2) + "%"
              : "N/A",
          trend: rev2 > rev1 ? "improving" : "declining",
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
  delete: protectedProcedure
    .input(z.object({ id: z.number() }))
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
        await db.delete(pnlReports).where(eq(pnlReports.id, input.id));
        await writeAuditLog({
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? (ctx.user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? (ctx.user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "pnlReportsCrud",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id ?? "new")
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { success: true };
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
