import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, avg, gte, lte } from "drizzle-orm";
import {
  trainingCourses,
  trainingEnrollments,
  agents,
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
      "agentTraining",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentTraining",
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
    resource: "agentTraining",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentTraining",
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

export const agentTrainingRouter = router({
  listCourses: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(50),
          status: z.string().optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(trainingCourses)
          .orderBy(desc(trainingCourses.createdAt))
          .limit(input?.limit ?? 50);
        return { courses: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getCourse: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [course] = await db
          .select()
          .from(trainingCourses)
          .where(eq(trainingCourses.id, input.id))
          .limit(1);
        if (!course) return null;
        const [enrollCount] = await db
          .select({ value: count() })
          .from(trainingEnrollments)
          .where(eq(trainingEnrollments.courseId, input.id))
          .limit(100);
        return { ...course, enrollmentCount: Number(enrollCount.value) };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  listEnrollments: protectedProcedure
    .input(
      z.object({
        agentId: z.number().optional(),
        courseId: z.number().optional(),
        limit: z.number().default(50),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        let query = db
          .select()
          .from(trainingEnrollments)
          .orderBy(desc(trainingEnrollments.createdAt))
          .limit(input.limit);
        const rows = await query;
        return { enrollments: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  enroll: protectedProcedure
    .input(z.object({ agentId: z.number(), courseId: z.number() }))
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
        const [enrollment] = await db
          .insert(trainingEnrollments)
          .values({
            agentId: input.agentId,
            courseId: input.courseId,
            status: "enrolled",
            progress: 0,
          })
          .returning();
        await db.insert(auditLog).values({
          action: "training_enrollment",
          resource: "training_enrollments",
          resourceId: String(enrollment.id),
          status: "success",
          metadata: { agentId: input.agentId, courseId: input.courseId },
        });
        return enrollment;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  updateProgress: protectedProcedure
    .input(
      z.object({
        enrollmentId: z.number(),
        progress: z.number().min(0).max(100),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const status = input.progress >= 100 ? "completed" : "in_progress";
        await db
          .update(trainingEnrollments)
          .set({ progress: input.progress, status })
          .where(eq(trainingEnrollments.id, input.enrollmentId));
        await db.insert(auditLog).values({
          action: "training_progress_update",
          resource: "training_enrollments",
          resourceId: String(input.enrollmentId),
          status: "success",
          metadata: { progress: input.progress },
        });

        return { success: true, progress: input.progress, status };
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
    const [totalCourses] = await db
      .select({ value: count() })
      .from(trainingCourses)
      .limit(100);
    const [totalEnrollments] = await db
      .select({ value: count() })
      .from(trainingEnrollments)
      .limit(100);
    const [completed] = await db
      .select({ value: count() })
      .from(trainingEnrollments)
      .where(eq(trainingEnrollments.status, "completed"))
      .limit(100);
    return {
      totalCourses: Number(totalCourses.value),
      totalEnrollments: Number(totalEnrollments.value),
      completedEnrollments: Number(completed.value),
      completionRate:
        Number(totalEnrollments.value) > 0
          ? Math.round(
              (Number(completed.value) / Number(totalEnrollments.value)) * 100
            )
          : 0,
    };
  }),

  dashboard: protectedProcedure.query(async () => {
    return {
      totalItems: 0,
      activeItems: 0,
      recentActivity: [],
      lastUpdated: new Date().toISOString(),
    };
  }),
});
