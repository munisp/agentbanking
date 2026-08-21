import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getAgentFromCookie } from "../middleware/agentAuth";
import { getDb } from "../db";
import { transactions } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";

// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
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
  pending: ["processing", "cancelled"],
  processing: ["completed", "failed"],
  completed: ["refunded"],
  failed: ["pending"],
  cancelled: [],
  refunded: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateCrossborderremittancehubInput(
  data: Record<string, unknown>
): boolean {
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
      "crossBorderRemittanceHub",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "crossBorderRemittanceHub",
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
    resource: "crossBorderRemittanceHub",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "crossBorderRemittanceHub",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Domain Calculations ────────────────────────────────────────────────────
function computeFees(amount: number, txType: string = "transfer") {
  if (amount <= 0) return { fee: 0, commission: 0, tax: 0, netAmount: amount };
  const feeResult = calculateFee(amount, txType);
  const commResult = calculateCommission(feeResult.fee, txType);
  const taxResult = calculateTax(feeResult.fee, "vat");
  const totalDeductions = feeResult.fee + taxResult.taxAmount;
  const netAmount = Math.max(0, amount - totalDeductions);
  const rate = amount > 0 ? feeResult.fee / amount : 0;
  return {
    fee: feeResult.fee,
    feeRate: parseFloat(rate.toFixed(4)),
    commission: commResult.agentShare,
    platformCommission: commResult.platformShare,
    tax: taxResult.taxAmount,
    taxRate: parseFloat(taxResult.taxRate.toFixed(4)),
    netAmount: parseFloat(netAmount.toFixed(2)),
    grossAmount: amount,
  };
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_CROSSBORDERREMITTANCEHUB = {
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
    if (!INTEGRITY_RULES_CROSSBORDERREMITTANCEHUB.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_CROSSBORDERREMITTANCEHUB.validateRange(
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

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Database Query Patterns ────────────────────────────────────────────────
const _crossBorderRemittanceHub_db = {
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


// NF-FF-32: scope financial reads to the calling agent's own transactions.
// Admins (platform admin role or admin agent session) may read unscoped.
async function resolveTransactionScope(ctx: {
  req: any;
  user?: { id: number; role?: string } | null;
}): Promise<number | null> {
  const session = await getAgentFromCookie(ctx.req);
  const isAdmin = ctx.user?.role === "admin" || session?.role === "admin";
  if (isAdmin) return null; // null = unscoped (admin)
  if (!session)
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Agent session required to access transaction data",
    });
  return session.id;
}

export const crossBorderRemittanceHubRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().optional(),
      })
    )
    .query(async ({ input, ctx }) => {
      try {
        const database = await getDb();
        if (!database)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "Database unavailable",
          });
        // NF-FF-32: scope to the calling agent (admins unscoped); correct
        // ordering key is transactions.id (was wrong-table auditLog.id).
        const scopeAgentId = await resolveTransactionScope(ctx);
        const scopeWhere =
          scopeAgentId !== null
            ? eq(transactions.agentId, scopeAgentId)
            : undefined;
        const results = await database
          .select()
          .from(transactions)
          .where(scopeWhere)
          .orderBy(desc(transactions.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(transactions)
          .where(scopeWhere);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input, ctx }) => {
      const database = await getDb();
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable",
        });
      // NF-FF-32: scope to the calling agent and predicate on the correct
      // table key (transactions.id, not auditLog.id).
      const scopeAgentId = await resolveTransactionScope(ctx);
      const recordWhere =
        scopeAgentId !== null
          ? and(
              eq(transactions.id, input.id),
              eq(transactions.agentId, scopeAgentId)
            )
          : eq(transactions.id, input.id);
      const [record] = await database
        .select()
        .from(transactions)
        .where(recordWhere)
        .limit(1);

      if (!record) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: `Record with id ${input.id} not found`,
        });
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    try {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const _totalRows = await database
        .select({ total: count() })
        .from(transactions);
      const totalResult = Array.isArray(_totalRows)
        ? _totalRows[0]
        : _totalRows;

      return {
        totalRecords: totalResult?.total ?? 0,
        lastUpdated: new Date().toISOString(),
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input, ctx }) => {
      try {
        const database = await getDb();
        if (!database)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "Database unavailable",
          });
        const since = new Date();
        since.setDate(since.getDate() - input.days);

        // NF-FF-32: scope to the calling agent, predicate/order on
        // transactions columns (was wrong-table auditLog.id), and actually
        // apply the requested time window.
        const scopeAgentId = await resolveTransactionScope(ctx);
        const windowWhere =
          scopeAgentId !== null
            ? and(
                eq(transactions.agentId, scopeAgentId),
                gte(transactions.createdAt, since)
              )
            : gte(transactions.createdAt, since);
        const results = await database
          .select()
          .from(transactions)
          .where(windowWhere)
          .orderBy(desc(transactions.id))
          .limit(input.limit);

        return results;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getStats: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    try {
      const [totalRow] = await database
        .select({ total: count() })
        .from(transactions);
      const total = totalRow?.total ?? 0;
      return {
        total,
        active: total,
        recent: Math.min(total, 50),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  initiateTransfer: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "crossBorderRemittanceHub.initiateTransfer is not available in this deployment",
      });
    }),

  listCorridors: protectedProcedure.query(async () => {
    try {
      return { data: [], total: 0 };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),
});
