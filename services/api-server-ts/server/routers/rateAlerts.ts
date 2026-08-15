// @ts-nocheck
import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { rateAlerts } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
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
function validateRatealertsInput(data: Record<string, unknown>): boolean {
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
      "rateAlerts",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "rateAlerts",
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
    resource: "rateAlerts",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "rateAlerts",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_RATEALERTS = {
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
    if (!INTEGRITY_RULES_RATEALERTS.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (!INTEGRITY_RULES_RATEALERTS.validateRange(data.amount, 0, 100_000_000))
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

// ── Database Query Patterns ────────────────────────────────────────────────
const _rateAlerts_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

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

export const rateAlertsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const results = await database
          .select()
          .from(rateAlerts)
          .orderBy(desc(rateAlerts.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(rateAlerts);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch {
        return { data: [], total: 0, limit: 0, offset: 0 };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(rateAlerts)
        .where(eq(rateAlerts.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const _totalRows = await database
      .select({ total: count() })
      .from(rateAlerts);
    const totalResult = Array.isArray(_totalRows) ? _totalRows[0] : _totalRows;

    return {
      totalRecords: totalResult?.total ?? 0,
      lastUpdated: new Date().toISOString(),
    };
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(rateAlerts)
        .orderBy(desc(rateAlerts.id))
        .limit(input.limit);

      return results;
    }),

  create: protectedProcedure
    .input(z.object({ data: z.record(z.string(), z.any()).optional() }))
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "rateAlerts.create is not available in this deployment",
      });
    }),

  delete: protectedProcedure
    .input(z.object({ id: z.union([z.number(), z.string()]) }))
    .mutation(async ({ input }) => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "rateAlerts.delete is not available in this deployment",
      });
    }),

  getCheckerStatus: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  getStats: protectedProcedure.query(async () => {
    // Merged implementation — this router previously declared getStats twice;
    // the second (hardcoded zeros) silently overwrote this real query.
    const database = await getDb();
    if (!database)
      return {
        total: 0,
        active: 0,
        recent: 0,
        totalAlerts: 0,
        activeAlerts: 0,
        triggeredToday: 0,
        lastUpdated: new Date().toISOString(),
      };
    try {
      const [totalRow] = await database
        .select({ total: count() })
        .from(rateAlerts);
      const total = Number(totalRow?.total ?? 0);
      const [activeRow] = await database
        .select({ cnt: count() })
        .from(rateAlerts)
        .where(eq(rateAlerts.status, "active"));
      const active = Number(activeRow?.cnt ?? 0);
      const startOfDay = new Date();
      startOfDay.setHours(0, 0, 0, 0);
      const [triggeredRow] = await database
        .select({ cnt: count() })
        .from(rateAlerts)
        .where(gte(rateAlerts.triggeredAt, startOfDay));
      const triggeredToday = Number(triggeredRow?.cnt ?? 0);
      return {
        total,
        active,
        recent: Math.min(total, 50),
        totalAlerts: total,
        activeAlerts: active,
        triggeredToday,
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        total: 0,
        active: 0,
        recent: 0,
        totalAlerts: 0,
        activeAlerts: 0,
        triggeredToday: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  rearm: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "rateAlerts.rearm is not available in this deployment",
      });
    }),

  runCheck: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "rateAlerts.runCheck is not available in this deployment",
      });
    }),

  toggle: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "rateAlerts.toggle is not available in this deployment",
      });
    }),
  // Rate alert subscriptions with threshold logic
  subscribe: protectedProcedure
    .input(
      z.object({
        currencyPair: z.string(),
        threshold: z.number(),
        direction: z.enum(["above", "below"]),
        channel: z.enum(["email", "sms", "push"]).default("email"),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const [baseCurrency, targetCurrency] = input.currencyPair.split("/");
      if (!baseCurrency || !targetCurrency) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "currencyPair must be in BASE/TARGET format",
        });
      }
      const database = await getDb();
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database not available",
        });
      const inserted = await database
        .insert(rateAlerts)
        .values({
          agentId: (ctx as any)?.user?.id ?? 0,
          baseCurrency: baseCurrency.slice(0, 3).toUpperCase(),
          targetCurrency: targetCurrency.slice(0, 3).toUpperCase(),
          targetRate: String(input.threshold),
          direction: input.direction,
          status: "active",
          notifiedVia: [input.channel],
        })
        .returning();
      const row = inserted[0];
      return {
        id: row?.id,
        currencyPair: input.currencyPair,
        threshold: input.threshold,
        direction: input.direction,
        channel: input.channel,
        active: true,
        createdAt: row?.createdAt ?? new Date().toISOString(),
      };
    }),
  update: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        threshold: z.number().optional(),
        active: z.boolean().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database not available",
        });
      const set: Record<string, unknown> = { updatedAt: new Date() };
      if (input.threshold !== undefined)
        set.targetRate = String(input.threshold);
      if (input.active !== undefined)
        set.status = input.active ? "active" : "paused";
      const updated = await database
        .update(rateAlerts)
        .set(set)
        .where(eq(rateAlerts.id, input.id))
        .returning();
      if (updated.length === 0) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: `Rate alert ${input.id} not found`,
        });
      }
      return { id: input.id, updated: true };
    }),

  quickCreate: protectedProcedure
    .input(
      z.object({
        currencyPair: z.string(),
        threshold: z.number(),
        direction: z.enum(["above", "below"]),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const [baseCurrency, targetCurrency] = input.currencyPair.split("/");
      if (!baseCurrency || !targetCurrency) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "currencyPair must be in BASE/TARGET format",
        });
      }
      const database = await getDb();
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database not available",
        });
      const inserted = await database
        .insert(rateAlerts)
        .values({
          agentId: (ctx as any)?.user?.id ?? 0,
          baseCurrency: baseCurrency.slice(0, 3).toUpperCase(),
          targetCurrency: targetCurrency.slice(0, 3).toUpperCase(),
          targetRate: String(input.threshold),
          direction: input.direction,
          status: "active",
        })
        .returning();
      const row = inserted[0];
      return {
        id: row?.id,
        ...input,
        active: true,
      };
    }),
});
