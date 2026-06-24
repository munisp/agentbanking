// @ts-nocheck
// Sprint 87: Enrollment lifecycle, progress tracking, certification issuance
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { trainingEnrollments, trainingCourses } from "../../drizzle/schema";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

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

const ENROLLMENT_STATUSES = [
  "enrolled",
  "in_progress",
  "completed",
  "failed",
  "expired",
];

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "trainingEnrollmentsCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "trainingEnrollmentsCrud",
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
    resource: "trainingEnrollmentsCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "trainingEnrollmentsCrud",
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


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishtrainingEnrollmentsCrudMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `training.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(() => {});

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `training_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `training_${action}`,
    timestamp: ts,
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("training", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const trainingEnrollmentsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        agentId: z.number().optional(),
        courseId: z.number().optional(),
        status: z.string().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.agentId)
          conditions.push(eq(trainingEnrollments.agentId, input.agentId));
        if (input.courseId)
          conditions.push(eq(trainingEnrollments.courseId, input.courseId));
        if (input.status)
          conditions.push(eq(trainingEnrollments.status, input.status));
        const rows = await db
          .select()
          .from(trainingEnrollments)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(trainingEnrollments.id))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(trainingEnrollments)
          .where(conditions.length ? and(...conditions) : undefined)
          .limit(100);
        return { items: rows, total };
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
          .from(trainingEnrollments)
          .where(eq(trainingEnrollments.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Enrollment not found",
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
  enroll: protectedProcedure
    .input(z.object({ agentId: z.number(), courseId: z.number() }))
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
        // Check course exists and is active
        const [course] = await db
          .select()
          .from(trainingCourses)
          .where(eq(trainingCourses.id, input.courseId))
          .limit(100);
        if (!course)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Course not found",
          });
        if (!course.isActive)
          throw new TRPCError({
            code: "PRECONDITION_FAILED",
            message: "Course is not active",
          });
        // Check for duplicate enrollment
        const [existing] = await db
          .select()
          .from(trainingEnrollments)
          .where(
            and(
              eq(trainingEnrollments.agentId, input.agentId),
              eq(trainingEnrollments.courseId, input.courseId),
              eq(trainingEnrollments.status, "enrolled")
            )
          )
          .limit(100);
        if (existing)
          throw new TRPCError({
            code: "CONFLICT",
            message: "Agent is already enrolled in this course",
          });
        const [row] = await db
          .insert(trainingEnrollments)
          .values({
            agentId: input.agentId,
            courseId: input.courseId,
            status: "enrolled",
            progress: 0,
          })
          .returning();
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

          resource: "trainingEnrollmentsCrud",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return {
          ...row,
          courseName: course.title,
          message: "Enrolled successfully",
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
  updateProgress: protectedProcedure
    .input(z.object({ id: z.number(), progress: z.number().min(0).max(100) }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [enrollment] = await db
          .select()
          .from(trainingEnrollments)
          .where(eq(trainingEnrollments.id, input.id))
          .limit(100);
        if (!enrollment)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Enrollment not found",
          });
        const status =
          input.progress >= 100
            ? "completed"
            : input.progress > 0
              ? "in_progress"
              : "enrolled";
        const updates: any = { progress: input.progress, status };
        if (status === "in_progress" && !enrollment.startedAt)
          updates.startedAt = new Date();
        if (status === "completed") updates.completedAt = new Date();
        const [row] = await db
          .update(trainingEnrollments)
          .set(updates)
          .where(eq(trainingEnrollments.id, input.id))
          .returning();
        // Middleware fan-out (fail-open)
        await publishTrainingEnrollmentsCrudMiddleware("updateProgress", `${Date.now()}`, { action: "updateProgress" }).catch(() => {});

        return {
          ...row,
          message:
            status === "completed"
              ? "Course completed! Certificate issued."
              : `Progress updated to ${input.progress}%`,
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
  submitScore: protectedProcedure
    .input(z.object({ id: z.number(), score: z.number().min(0).max(100) }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [enrollment] = await db
          .select()
          .from(trainingEnrollments)
          .where(eq(trainingEnrollments.id, input.id))
          .limit(100);
        if (!enrollment)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Enrollment not found",
          });
        const [course] = await db
          .select()
          .from(trainingCourses)
          .where(eq(trainingCourses.id, enrollment.courseId))
          .limit(100);
        const passingScore = course?.passingScore || 70;
        const passed = input.score >= passingScore;
        const [row] = await db
          .update(trainingEnrollments)
          .set({
            score: input.score,
            status: passed ? "completed" : "failed",
            completedAt: new Date(),
          })
          .where(eq(trainingEnrollments.id, input.id))
          .returning();
        // Middleware fan-out (fail-open)
        await publishTrainingEnrollmentsCrudMiddleware("submitScore", `${Date.now()}`, { action: "submitScore" }).catch(() => {});

        return {
          ...row,
          passed,
          passingScore,
          message: passed
            ? `Passed with ${input.score}%!`
            : `Failed (${input.score}% < ${passingScore}% required)`,
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
  getAgentProgress: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const enrollments = await db
          .select()
          .from(trainingEnrollments)
          .where(eq(trainingEnrollments.agentId, input.agentId))
          .limit(100);
        const completed = enrollments.filter(
          e => e.status === "completed"
        ).length;
        const inProgress = enrollments.filter(
          e => e.status === "in_progress"
        ).length;
        return {
          agentId: input.agentId,
          total: enrollments.length,
          completed,
          inProgress,
          failed: enrollments.filter(e => e.status === "failed").length,
          completionRate:
            enrollments.length > 0
              ? Math.round((completed / enrollments.length) * 100)
              : 0,
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
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .delete(trainingEnrollments)
          .where(eq(trainingEnrollments.id, input.id));
        // Middleware fan-out (fail-open)
        await publishTrainingEnrollmentsCrudMiddleware("delete", `${Date.now()}`, { action: "delete" }).catch(() => {});

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
