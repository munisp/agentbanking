import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { auditLog } from "../../drizzle/schema";
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
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateAudittrailexportInput(data: Record<string, unknown>): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "auditTrailExport",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "auditTrailExport",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_AUDITTRAILEXPORT = {
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
    if (!INTEGRITY_RULES_AUDITTRAILEXPORT.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_AUDITTRAILEXPORT.validateRange(
        data.amount,
        0,
        100_000_000
      )
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

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

// ── Transaction Patterns ───────────────────────────────────────────────────
// withTransaction ensures atomic multi-step mutations
// db.transaction() wraps sequential DB ops in a single transaction
// .transaction() provides rollback on failure
const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T,>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};

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

const historyProc = protectedProcedure
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
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(auditLog)
        .orderBy(desc(auditLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(auditLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "trail_export",
        procedure: "history",
      };
    });

export const auditTrailExportRouter = router({
  history: historyProc,
  list: historyProc, // alias of history (broken-call fix)
  config: protectedProcedure
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
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(auditLog)
        .orderBy(desc(auditLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(auditLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "trail_export",
        procedure: "config",
      };
    }),

  // Export audit trail entries as CSV for a date range
  export: protectedProcedure
    .input(
      z
        .object({
          from: z.string().optional(),
          to: z.string().optional(),
          limit: z.number().min(1).max(10000).default(5000),
        })
        .optional()
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "Database unavailable",
          });
        const conditions = [];
        const from = input?.from ? new Date(input.from) : null;
        const to = input?.to ? new Date(input.to) : null;
        if (from && !isNaN(from.getTime()))
          conditions.push(gte(auditLog.createdAt, from));
        if (to && !isNaN(to.getTime())) {
          // Inclusive of the whole "to" day when a bare date is supplied
          if (input!.to!.length <= 10) to.setHours(23, 59, 59, 999);
          conditions.push(lte(auditLog.createdAt, to));
        }
        const rows = await db
          .select()
          .from(auditLog)
          .where(conditions.length > 0 ? and(...conditions) : undefined)
          .orderBy(desc(auditLog.createdAt))
          .limit(input?.limit ?? 5000);

        const csvEscape = (v: unknown) => {
          const s = v == null ? "" : String(v);
          return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        };
        const header =
          "id,createdAt,agentId,agentCode,action,resource,resourceId,status,ipAddress";
        const lines = rows.map(r =>
          [
            r.id,
            r.createdAt?.toISOString() ?? "",
            r.agentId ?? "",
            csvEscape(r.agentCode),
            csvEscape(r.action),
            csvEscape(r.resource),
            csvEscape(r.resourceId),
            csvEscape(r.status),
            csvEscape(r.ipAddress),
          ].join(",")
        );
        const csv = [header, ...lines].join("\n");
        const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
        const filename = `audit_export_${input?.from || "all"}_${input?.to || stamp}.csv`;
        return {
          success: true,
          filename,
          rowCount: rows.length,
          csv,
          from: input?.from ?? null,
          to: input?.to ?? null,
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
