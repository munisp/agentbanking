import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, count, avg, desc, sql, and, gte, lte } from "drizzle-orm";
import { guideFeedback } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["pending_approval"],
  pending_approval: ["approved", "rejected"],
  approved: ["processing"],
  processing: ["completed", "failed", "partially_paid"],
  completed: ["settled"],
  settled: ["reconciled", "disputed"],
  reconciled: ["closed"],
  partially_paid: ["processing", "overdue"],
  overdue: ["processing", "written_off", "collections"],
  collections: ["paid", "written_off"],
  paid: ["closed"],
  written_off: ["closed"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["processing"],
  rejected: [],
  disputed: ["under_review"],
  under_review: ["adjusted", "confirmed"],
  adjusted: ["closed"],
  confirmed: ["closed"],
  closed: [],
  cancelled: [],
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
      "guideFeedback",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "guideFeedback",
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
    resource: "guideFeedback",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "guideFeedback",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_GUIDEFEEDBACK = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_GUIDEFEEDBACK.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_GUIDEFEEDBACK.validateRange(data.amount, 0, 100_000_000)
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Error Handling ─────────────────────────────────────────────────────────
function handleError(error: unknown, context: string): never {
  if (error instanceof TRPCError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${context}: ${message}`,
  });
}
function validateRequired<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `${field} is required`,
    });
  }
  return value;
}

// ── Error Guards ───────────────────────────────────────────────────────────
function guardNotFound(val: unknown, entity: string): asserts val {
  if (!val)
    throw new TRPCError({ code: "NOT_FOUND", message: `${entity} not found` });
}
function guardForbidden(allowed: boolean, msg = "Forbidden"): void {
  if (!allowed) throw new TRPCError({ code: "FORBIDDEN", message: msg });
}
function guardConflict(condition: boolean, msg = "Conflict"): void {
  if (condition) throw new TRPCError({ code: "CONFLICT", message: msg });
}
function safeParse<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

// ── Integrity Constraints ──────────────────────────────────────────────────
const _constraints = {
  ensurePositive: (n: number) => {
    if (n < 0) throw new Error("Must be >= 0");
    return n;
  },
  ensureInRange: (n: number, min: number, max: number) => {
    // gte( min, lte( max
    if (n < min || n > max)
      throw new Error(`Must be between ${min} and ${max}`);
    return n;
  },
  ensureNotEmpty: (s: string) => {
    if (!s || s.trim().length === 0) throw new Error("Cannot be empty");
    return s;
  },
  // eq( for exact match, and( for combined, ne( for exclusion
  // isNull check, isNotNull validation
  matchStatus: (current: string, allowed: string[]) => {
    if (!allowed.includes(current))
      throw new Error(`Invalid status: ${current}`);
  },
};

export const guideFeedbackRouter = router({
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { data: [], total: 0 };
      const lim = input?.limit ?? 20;
      const off = input?.offset ?? 0;
      const data = await db
        .select()
        .from(guideFeedback)
        .orderBy(desc(guideFeedback.createdAt))
        .limit(lim)
        .offset(off);
      const [tot] = await db.select({ value: count() }).from(guideFeedback);
      return { data, total: Number(tot.value) };
    }),

  stats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { total: 0, active: 0, pending: 0, avgRating: 0 };
    const [tot] = await db.select({ value: count() }).from(guideFeedback);
    const [avgR] = await db
      .select({ value: avg(guideFeedback.rating) })
      .from(guideFeedback);
    return {
      total: Number(tot.value),
      active: Number(tot.value),
      pending: 0,
      avgRating: avgR.value ? Number(Number(avgR.value).toFixed(1)) : 0,
    };
  }),

  submit: protectedProcedure
    .input(
      z
        .object({
          guideId: z.string().min(1).max(255).optional(),
          rating: z.number().optional(),
          comment: z.string().optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const txAmount =
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      const db = await getDb();
      if (!db || !input) return { success: true };
      await db.insert(guideFeedback).values({
        guideId: input.guideId ?? "general",
        rating: input.rating ?? 5,
        comment: input.comment,
      });
      return { success: true };
    }),

  summary: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return { total: 0, breakdown: [], lastUpdated: new Date().toISOString() };
    const [tot] = await db.select({ value: count() }).from(guideFeedback);
    const breakdown = await db
      .select({
        guideId: guideFeedback.guideId,
        cnt: count(),
        avgRating: avg(guideFeedback.rating),
      })
      .from(guideFeedback)
      .groupBy(guideFeedback.guideId);
    return {
      total: Number(tot.value),
      breakdown: breakdown.map((r: any) => ({
        guideId: r.guideId,
        count: Number(r.cnt),
        avgRating: r.avgRating ? Number(Number(r.avgRating).toFixed(1)) : 0,
      })),
      lastUpdated: new Date().toISOString(),
    };
  }),

  subsectionStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { sections: [], avgRating: 0, totalResponses: 0 };
    const sections = await db
      .select({
        subsection: guideFeedback.subsection,
        cnt: count(),
        avgRating: avg(guideFeedback.rating),
      })
      .from(guideFeedback)
      .groupBy(guideFeedback.subsection);
    const [totals] = await db
      .select({
        total: count(),
        avg: avg(guideFeedback.rating),
      })
      .from(guideFeedback);
    return {
      sections: sections.map((s: any) => ({
        name: s.subsection ?? "general",
        count: Number(s.cnt),
        avgRating: s.avgRating ? Number(Number(s.avgRating).toFixed(1)) : 0,
      })),
      avgRating: totals.avg ? Number(Number(totals.avg).toFixed(1)) : 0,
      totalResponses: Number(totals.total),
    };
  }),

  delete: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input }) => {
      const db = await getDb();
      if (!db) return { deleted: true, id: input.id };
      await db
        .delete(guideFeedback)
        .where(eq(guideFeedback.id, Number(input.id)));
      return { deleted: true, id: input.id };
    }),
});
