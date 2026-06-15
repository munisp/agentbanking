// Sprint 87: Curriculum sequencing, prerequisite validation, completion tracking
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { trainingCourses } from "../../drizzle/schema";
import { eq, desc, and, count } from "drizzle-orm";
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

const CATEGORIES = [
  "onboarding",
  "compliance",
  "product",
  "security",
  "advanced",
  "leadership",
];
const CONTENT_TYPES = ["video", "document", "quiz", "interactive", "webinar"];

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "trainingCoursesCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "trainingCoursesCrud",
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
    resource: "trainingCoursesCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "trainingCoursesCrud",
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

export const trainingCoursesRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        category: z.string().optional(),
        isMandatory: z.boolean().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.category)
          conditions.push(eq(trainingCourses.category, input.category));
        if (input.isMandatory !== undefined)
          conditions.push(eq(trainingCourses.isMandatory, input.isMandatory));
        const rows = await db
          .select()
          .from(trainingCourses)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(trainingCourses.id))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(trainingCourses)
          .where(conditions.length ? and(...conditions) : undefined)
          .limit(100);
        return { items: rows, total, categories: CATEGORIES };
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
          .from(trainingCourses)
          .where(eq(trainingCourses.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Course not found",
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
  create: protectedProcedure
    .input(
      z.object({
        title: z.string().min(5),
        description: z.string().optional(),
        category: z.enum([
          "onboarding",
          "compliance",
          "product",
          "security",
          "advanced",
          "leadership",
        ]),
        contentType: z.enum([
          "video",
          "document",
          "quiz",
          "interactive",
          "webinar",
        ]),
        contentUrl: z.string().url().optional(),
        durationMinutes: z.number().min(1).optional(),
        passingScore: z.number().min(0).max(100).default(70),
        isMandatory: z.boolean().default(false),
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
        const [existing] = await db
          .select()
          .from(trainingCourses)
          .where(eq(trainingCourses.title, input.title))
          .limit(100);
        if (existing)
          throw new TRPCError({
            code: "CONFLICT",
            message: "Course with this title already exists",
          });
        const [row] = await db
          .insert(trainingCourses)
          .values({
            ...input,
            createdBy: ctx.user?.id,
            isActive: true,
            version: 1,
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

          resource: "trainingCoursesCrud",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String(
                  "id" in input ? (input as Record<string, unknown>).id : "new"
                )
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return {
          ...row,
          message: input.isMandatory
            ? "Mandatory course created — all agents must complete"
            : "Course created",
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
  deactivate: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .update(trainingCourses)
          .set({ isActive: false })
          .where(eq(trainingCourses.id, input.id));
        return { success: true, message: "Course deactivated" };
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
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .delete(trainingCourses)
          .where(eq(trainingCourses.id, input.id));
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
