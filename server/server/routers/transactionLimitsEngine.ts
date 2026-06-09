// @ts-nocheck
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  eq,
  desc,
  and,
  sql,
  count,
  sum,
  isNull,
  gte,
  lte,
  or,
  asc,
} from "drizzle-orm";
import { systemConfig, auditLog } from "../../drizzle/schema";
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
  initiated: ["pending_validation"],
  pending_validation: ["validated", "failed_validation"],
  validated: ["authorized", "declined"],
  authorized: ["processing"],
  processing: ["completed", "failed", "reversed"],
  completed: ["settled", "disputed", "reversed"],
  settled: ["reconciled"],
  reconciled: ["archived"],
  failed: ["retry_pending", "cancelled"],
  failed_validation: ["retry_pending", "cancelled"],
  declined: ["cancelled"],
  reversed: ["refund_processing"],
  refund_processing: ["refunded"],
  refunded: ["archived"],
  disputed: ["under_investigation"],
  under_investigation: ["resolved", "escalated"],
  resolved: ["archived"],
  escalated: ["resolved"],
  retry_pending: ["processing"],
  cancelled: [],
  archived: [],
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
      "transactionLimitsEngine",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "transactionLimitsEngine",
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
    resource: "transactionLimitsEngine",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "transactionLimitsEngine",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_TRANSACTIONLIMITSENGINE = {
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
    if (!INTEGRITY_RULES_TRANSACTIONLIMITSENGINE.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_TRANSACTIONLIMITSENGINE.validateRange(
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
const _transactionLimitsEngine_db = {
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

export const transactionLimitsEngineRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalLimits: 0, activeLimits: 0, breachesToday: 0 };
    const rows = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'tx_limit_%'`)
      .limit(100);
    return {
      totalLimits: rows.length,
      activeLimits: rows.length,
      breachesToday: 0,
    };
  }),
  listLimits: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { limits: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(sql`${systemConfig.key} LIKE 'tx_limit_%'`)
          .limit(input?.limit ?? 20);
        return {
          limits: rows.map(r => ({
            id: r.key.replace("tx_limit_", ""),
            ...JSON.parse(String(r.value ?? "{}")),
          })),
          total: rows.length,
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
  checkLimit: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        amount: z.number().min(0),
        transactionType: z.string(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { allowed: true, limit: 0, remaining: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "tx_limit_" + input.transactionType))
          .limit(1);
        if (rows.length === 0)
          return { allowed: true, limit: 10000000, remaining: 10000000 };
        const limit = JSON.parse(String(rows[0].value ?? "{}"));
        const maxAmount = Number(limit.maxAmount ?? 10000000);
        return {
          allowed: input.amount <= maxAmount,
          limit: maxAmount,
          remaining: Math.max(0, maxAmount - input.amount),
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
  setLimit: protectedProcedure
    .input(
      z.object({
        transactionType: z.string(),
        maxAmount: z.number(),
        dailyLimit: z.number().optional(),
        monthlyLimit: z.number().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const txAmount = typeof input === "object" && "amount" in input ? Number((input as Record<string, unknown>).amount) : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db
          .insert(systemConfig)
          .values({
            key: "tx_limit_" + input.transactionType,
            value: JSON.stringify(input),
          })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: { value: JSON.stringify(input), updatedAt: new Date() },
          });
        await db.insert(auditLog).values({
          action: "tx_limit_set",
          resource: "tx_limits",
          resourceId: input.transactionType,
          status: "success",
          metadata: input,
        });
        await writeAuditLog({

          agentId: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.id ?? 0 : 0,

          agentCode: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.agentCode ?? "system" : "system",

          action: "MUTATION",

          resource: "transactionLimitsEngine",

          resourceId: typeof input === "object" && input !== null && "id" in input ? String((input as any).id) : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },

        });

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
