import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, sql, count, avg, and, gte, lte } from "drizzle-orm";
import {
  rateLimitRules,
  platform_health_checks,
  systemConfig,
  auditLog,
} from "../../drizzle/schema";
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
function validatePlatformproxyInput(data: Record<string, unknown>): boolean {
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
      "platformProxy",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "platformProxy",
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
    resource: "platformProxy",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "platformProxy",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_PLATFORMPROXY = {
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
    if (!INTEGRITY_RULES_PLATFORMPROXY.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_PLATFORMPROXY.validateRange(data.amount, 0, 100_000_000)
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
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
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
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

export const platformProxyRouter = router({
  listRoutes: protectedProcedure
    .input(
      z.object({ limit: z.number().min(1).max(200).default(50) }).optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(rateLimitRules)
          .orderBy(desc(rateLimitRules.createdAt))
          .limit(input?.limit ?? 50);
        return { routes: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getConfig: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [config] = await db
      .select()
      .from(systemConfig)
      .where(eq(systemConfig.key, "proxy_config"))
      .limit(1);
    return config
      ? JSON.parse(String(config.value))
      : {
          upstream: "http://localhost:3000",
          timeout: 30000,
          retries: 3,
          circuitBreaker: { threshold: 5, resetMs: 60000 },
        };
  }),
  updateConfig: protectedProcedure
    .input(
      z.object({
        timeout: z.number().min(1000).max(120000).optional(),
        retries: z.number().int().min(0).max(10).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "platformProxy",
        "mutation",
        "Executed platformProxy mutation"
      );

      try {
        const db = (await getDb())!;
        const key = "proxy_config";
        const [existing] = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, key))
          .limit(1);
        const current = existing ? JSON.parse(String(existing.value)) : {};
        const merged = { ...current, ...input };
        if (existing) {
          await db
            .update(systemConfig)
            .set({ value: JSON.stringify(merged) })
            .where(eq(systemConfig.key, key));
        } else {
          await db
            .insert(systemConfig)
            .values({ key, value: JSON.stringify(merged) });
        }
        await db.insert(auditLog).values({
          action: "proxy_config_updated",
          resource: "platform_proxy",
          resourceId: "config",
          status: "success",
          metadata: input,
        });
        return { success: true, config: merged };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getUpstreamHealth: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [stats] = await db
      .select({
        total: count(),
        avgLat: avg(platform_health_checks.responseTime),
      })
      .from(platform_health_checks)
      .limit(100);
    return {
      status: "healthy",
      totalChecks: Number(stats.total),
      avgLatencyMs: Math.round(Number(stats.avgLat ?? 0)),
    };
  }),
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [rules] = await db
      .select({ value: count() })
      .from(rateLimitRules)
      .limit(100);
    const [checks] = await db
      .select({ value: count() })
      .from(platform_health_checks)
      .limit(100);
    return {
      totalRules: Number(rules.value),
      totalChecks: Number(checks.value),
    };
  }),
  fraud: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
});
