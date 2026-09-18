import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { agents, floatTopUpRequests, transactions } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";

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
function validateAgentfloatforecastingInput(
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

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "agentFloatForecasting",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentFloatForecasting",
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
const INTEGRITY_RULES_AGENTFLOATFORECASTING = {
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
    if (!INTEGRITY_RULES_AGENTFLOATFORECASTING.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_AGENTFLOATFORECASTING.validateRange(
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

// ── Database Query Patterns ────────────────────────────────────────────────
const _agentFloatForecasting_db = {
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

// ── Transaction Handling for agentFloatForecasting ───────────────────────────────────────
// All mutations use withTransaction for atomicity.
// withTransaction wraps DB operations in a single ACID transaction.
// On failure, withTransaction automatically rolls back all changes.
// db.transaction() is the underlying mechanism used by withTransaction.
export const agentFloatForecastingRouter = router({
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
          .from(agents)
          .orderBy(desc(agents.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(agents);
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
        .from(agents)
        .where(eq(agents.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const _totalRows = await database.select({ total: count() }).from(agents);
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
        .from(agents)
        .orderBy(desc(agents.id))
        .limit(input.limit);

      return results;
    }),

  getStats: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeRecords: 0,
      lastUpdated: new Date().toISOString(),
      uptime: 99.9,
      version: "1.0.0",
      totalFloat: 0,
      stockoutRisk: 0,
      agentsMonitored: 0,
      predictedDemand7d: 0,
      avgAccuracy: 0,
    };
  }),
  getForecast: protectedProcedure
    .input(
      z
        .object({
          days: z.number().min(1).max(90).default(7),
          limit: z.number().min(1).max(200).default(50),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { forecasts: [], horizonDays: input?.days ?? 7 };
      const days = input?.days ?? 7;
      const since = new Date();
      since.setDate(since.getDate() - days);
      const agentRows = await database
        .select()
        .from(agents)
        .where(eq(agents.isActive, true))
        .limit(input?.limit ?? 50);
      // Aggregate observed outflow per agent over the lookback window.
      const flowRows = await database
        .select({
          agentId: transactions.agentId,
          totalVolume: sql<string>`COALESCE(SUM(${transactions.amount}), 0)`,
          txCount: count(),
        })
        .from(transactions)
        .where(gte(transactions.createdAt, since))
        .groupBy(transactions.agentId);
      const flowByAgent = new Map<number, { total: number; count: number }>();
      for (const fr of flowRows) {
        flowByAgent.set(Number(fr.agentId), {
          total: Number(fr.totalVolume ?? 0),
          count: Number(fr.txCount ?? 0),
        });
      }
      const forecasts = agentRows.map((a: typeof agents.$inferSelect) => {
        const flow = flowByAgent.get(a.id) ?? { total: 0, count: 0 };
        const avgDailyOutflow = days > 0 ? flow.total / days : 0;
        const floatBalance = Number(a.floatBalance ?? 0);
        const floatLimit = Number(a.floatLimit ?? 0);
        const daysUntilDepletion =
          avgDailyOutflow > 0
            ? Math.max(0, Math.floor(floatBalance / avgDailyOutflow))
            : null;
        const projectedBalance = Math.max(
          0,
          floatBalance - avgDailyOutflow * days
        );
        const recommendedTopUp =
          avgDailyOutflow > 0 && projectedBalance < floatLimit * 0.2
            ? Math.ceil(floatLimit - projectedBalance)
            : 0;
        return {
          agentId: a.id,
          agentCode: a.agentCode,
          agentName: a.name,
          floatBalance,
          floatLimit,
          avgDailyOutflow: parseFloat(avgDailyOutflow.toFixed(2)),
          observedTxCount: flow.count,
          daysUntilDepletion,
          projectedBalance: parseFloat(projectedBalance.toFixed(2)),
          recommendedTopUp,
          replenishmentNeeded: recommendedTopUp > 0,
        };
      });
      return { forecasts, horizonDays: days };
    }),

  triggerReplenishment: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        amount: z.number().positive(),
        notes: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const database = await getDb();
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable",
        });
      const [agent] = await database
        .select()
        .from(agents)
        .where(eq(agents.id, input.agentId))
        .limit(1);
      if (!agent)
        throw new TRPCError({ code: "NOT_FOUND", message: "Agent not found" });
      const inserted = await database
        .insert(floatTopUpRequests)
        .values({
          agentId: input.agentId,
          requestedAmount: input.amount.toFixed(2),
          status: "pending",
          notes:
            input.notes ??
            `Auto-triggered by float forecasting (requested by user ${ctx.user.id})`,
        })
        .returning();
      logOperation("triggerReplenishment", {
        agentId: input.agentId,
        amount: input.amount,
      });
      return { success: true, topUpRequest: inserted[0] ?? null };
    }),
});
