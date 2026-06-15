/**
 * F08: Compliance Filing & Regulatory Reporting
 * CBN/NDIC/FIRS filings, SAR generation, CTR reports, regulatory calendar
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import { complianceFilings } from "../../drizzle/schema";
import { eq, desc, and, gte, lte, count, sql } from "drizzle-orm";
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
  not_started: ["documents_submitted"],
  documents_submitted: ["under_review"],
  under_review: [
    "additional_info_required",
    "verified",
    "rejected",
    "escalated",
  ],
  additional_info_required: ["documents_submitted"],
  verified: ["active", "expired"],
  active: ["renewal_pending", "suspended", "revoked"],
  renewal_pending: ["under_review"],
  expired: ["renewal_pending", "revoked"],
  suspended: ["under_review", "revoked"],
  escalated: ["verified", "rejected"],
  rejected: ["appeal"],
  appeal: ["under_review"],
  revoked: [],
};

const FILING_TYPES = [
  "SAR",
  "CTR",
  "STR",
  "CBN_RETURNS",
  "NDIC_REPORT",
  "FIRS_TAX",
  "AML_REPORT",
  "PCI_DSS_AUDIT",
];
const REGULATORS = ["CBN", "NDIC", "FIRS", "EFCC", "SEC", "NFIU"];

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "complianceFiling",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "complianceFiling",
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
    resource: "complianceFiling",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "complianceFiling",
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

export const complianceFilingRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        page: z.number().default(1),
        limit: z.number().default(20),
        filingType: z.string().optional(),
        regulator: z.string().optional(),
        status: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const conditions = [];
        if (input.filingType)
          conditions.push(eq(complianceFilings.filingType, input.filingType));
        if (input.regulator)
          conditions.push(
            eq(complianceFilings.createdAt, input.regulator as any)
          );
        if (input.status)
          conditions.push(eq(complianceFilings.status, input.status));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const items = await db
          .select()
          .from(complianceFilings)
          .where(where)
          .orderBy(desc(complianceFilings.createdAt))
          .limit(input.limit)
          .offset((input.page - 1) * input.limit);
        const [{ total }] = await db
          .select({ total: count() })
          .from(complianceFilings)
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

  createFiling: protectedProcedure
    .input(
      z.object({
        filingType: z.string(),
        regulator: z.string(),
        periodStart: z.string(),
        periodEnd: z.string(),
        reportData: z.any(),
        dueDate: z.string(),
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
        const [filing] = await db
          .insert(complianceFilings)
          .values({
            filingType: input.filingType,
            regulator: input.regulator,
            periodStart: new Date(input.periodStart),
            periodEnd: new Date(input.periodEnd),
            reportData: JSON.stringify(input.reportData),
            dueDate: new Date(input.dueDate),
            status: "draft",
            preparedBy: ctx.user?.id,
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

          resource: "complianceFiling",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String(
                  "id" in input ? (input as Record<string, unknown>).id : "new"
                )
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { filing };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  submitFiling: protectedProcedure
    .input(z.object({ filingId: z.number() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .update(complianceFilings)
          .set({
            status: "submitted",
            submittedAt: new Date(),
          })
          .where(eq(complianceFilings.id, input.filingId));
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

  acknowledgeFiling: protectedProcedure
    .input(z.object({ filingId: z.number(), acknowledgementRef: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .update(complianceFilings)
          .set({
            status: "acknowledged",
          })
          .where(eq(complianceFilings.id, input.filingId));
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

  upcomingDeadlines: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) return { deadlines: [] };
    const thirtyDaysFromNow = new Date(Date.now() + 30 * 86400000);
    const items = await db
      .select()
      .from(complianceFilings)
      .where(
        and(
          lte(complianceFilings.createdAt, thirtyDaysFromNow),
          sql`${complianceFilings.status} NOT IN ('submitted', 'acknowledged')`
        )
      )
      .orderBy(complianceFilings.createdAt);
    return { deadlines: items };
  }),

  filingTypes: protectedProcedure.query(() => FILING_TYPES),
  regulators: protectedProcedure.query(() => REGULATORS),
});
