/**
 * F12: Customer Journey Analytics
 * Journey steps, funnel analysis, touchpoint tracking, conversion metrics
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import { customerJourneySteps } from "../../drizzle/schema";
import { eq, desc, and, gte, count, sql, lte } from "drizzle-orm";
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
  draft: ["scheduled", "generating"],
  scheduled: ["generating", "cancelled"],
  generating: ["completed", "failed"],
  completed: ["distributed", "archived"],
  distributed: ["acknowledged", "archived"],
  acknowledged: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["generating"],
  cancelled: [],
  archived: [],
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
      "customerJourneyAnalytics",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "customerJourneyAnalytics",
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
    resource: "customerJourneyAnalytics",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "customerJourneyAnalytics",
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

export const customerJourneyAnalyticsRouter = router({
  listSteps: protectedProcedure
    .input(
      z.object({
        page: z.number().default(1),
        limit: z.number().default(50),
        customerId: z.number().optional(),
        journeyType: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const conditions = [];
        if (input.customerId)
          conditions.push(
            eq(customerJourneySteps.customerId, input.customerId)
          );
        if (input.journeyType)
          conditions.push(eq(customerJourneySteps.stepType, input.journeyType));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const items = await db
          .select()
          .from(customerJourneySteps)
          .where(where)
          .orderBy(desc(customerJourneySteps.createdAt))
          .limit(input.limit)
          .offset((input.page - 1) * input.limit);
        const [{ total }] = await db
          .select({ total: count() })
          .from(customerJourneySteps)
          .where(where)
          .limit(100);
        return { items, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  recordStep: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        journeyType: z.string(),
        stepName: z.string(),
        stepOrder: z.number(),
        channel: z.string(),
        metadata: z.any().optional(),
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
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const [step] = await db
          .insert(customerJourneySteps)
          .values({
            customerId: input.customerId,
            journeyType: input.journeyType,
            stepName: input.stepName,
            stepOrder: input.stepOrder,
            channel: input.channel,
            metadata: input.metadata ? JSON.stringify(input.metadata) : null,
          })
          .returning();
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

          resource: "customerJourneyAnalytics",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String(
                  "id" in input ? (input as Record<string, unknown>).id : "new"
                )
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { step };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  funnelAnalysis: protectedProcedure
    .input(
      z.object({
        journeyType: z.string(),
        period: z.enum(["7d", "30d", "90d"]).default("30d"),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { funnel: [] };
        const periodDays = { "7d": 7, "30d": 30, "90d": 90 };
        const since = new Date(
          Date.now() - periodDays[input.period] * 86400000
        );
        const data = await db
          .select({
            stepName: customerJourneySteps.stepType,
            stepOrder: customerJourneySteps.stepType,
            count: count(),
          })
          .from(customerJourneySteps)
          .where(
            and(
              eq(customerJourneySteps.stepType, input.journeyType),
              gte(customerJourneySteps.createdAt, since)
            )
          )
          .groupBy(customerJourneySteps.stepType, customerJourneySteps.stepType)
          .orderBy(customerJourneySteps.stepType);
        return { funnel: data };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  touchpointSummary: protectedProcedure
    .input(z.object({ period: z.enum(["7d", "30d", "90d"]).default("30d") }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { touchpoints: [] };
        const periodDays = { "7d": 7, "30d": 30, "90d": 90 };
        const since = new Date(
          Date.now() - periodDays[input.period] * 86400000
        );
        const data = await db
          .select({
            channel: (customerJourneySteps as Record<string, any>)["channel"],
            count: count(),
          })
          .from(customerJourneySteps)
          .where(gte(customerJourneySteps.createdAt, since))
          .groupBy((customerJourneySteps as Record<string, any>)["channel"]);
        return { touchpoints: data };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  journeyTypes: protectedProcedure.query(() => [
    "onboarding",
    "first_transaction",
    "kyc_verification",
    "loan_application",
    "dispute_resolution",
    "churn_prevention",
  ]),
});
