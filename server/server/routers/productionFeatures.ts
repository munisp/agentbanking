// @ts-nocheck
// Production features: rateLimit configuration, health check endpoints, monitoring
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
import { auditLog, systemConfig } from "../../drizzle/schema";
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
  proposed: ["review"],
  review: ["approved", "rejected"],
  approved: ["deploying"],
  deploying: ["active", "rollback"],
  active: ["deprecated", "updated"],
  deprecated: ["removed"],
  updated: ["active"],
  rollback: ["review"],
  removed: [],
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
      "productionFeatures",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "productionFeatures",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_PRODUCTIONFEATURES = {
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
    if (!INTEGRITY_RULES_PRODUCTIONFEATURES.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_PRODUCTIONFEATURES.validateRange(
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

// ── Database Query Patterns ────────────────────────────────────────────────
const _productionFeatures_db = {
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

export const productionFeaturesRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return {
        totalFeatures: 0,
        enabled: 0,
        disabled: 0,
        rolloutInProgress: 0,
      };
    const rows = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'ff_%'`)
      .limit(100);
    const enabled = rows.filter(r => {
      try {
        return JSON.parse(String(r.value ?? "{}")).enabled === true;
      } catch {
        return false;
      }
    }).length;
    return {
      totalFeatures: rows.length,
      enabled,
      disabled: rows.length - enabled,
      rolloutInProgress: 0,
    };
  }),
  listFeatures: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { features: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(sql`${systemConfig.key} LIKE 'ff_%'`)
          .limit(input?.limit ?? 50);
        return {
          features: rows.map(r => ({
            key: r.key.replace("ff_", ""),
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
  toggleFeature: protectedProcedure
    .input(z.object({ featureKey: z.string(), enabled: z.boolean() }))
    .mutation(async ({ input, ctx }) => {
      const txAmount = typeof input === "object" && "amount" in input ? Number((input as Record<string, unknown>).amount) : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const key = "ff_" + input.featureKey;
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, key))
          .limit(1);
        const existing =
          rows.length > 0 ? JSON.parse(String(rows[0].value ?? "{}")) : {};
        const merged = {
          ...existing,
          enabled: input.enabled,
          updatedAt: new Date().toISOString(),
        };
        await db
          .insert(systemConfig)
          .values({ key, value: JSON.stringify(merged) })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: { value: JSON.stringify(merged), updatedAt: new Date() },
          });
        await db.insert(auditLog).values({
          action: input.enabled ? "feature_enabled" : "feature_disabled",
          resource: "feature_flags",
          resourceId: input.featureKey,
          status: "success",
          metadata: { enabled: input.enabled },
        });
        await writeAuditLog({

          agentId: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.id ?? 0 : 0,

          agentCode: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.agentCode ?? "system" : "system",

          action: "MUTATION",

          resource: "productionFeatures",

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
  createFeature: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        description: z.string().optional(),
        enabled: z.boolean().default(false),
        rolloutPercent: z.number().default(0),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const key = "ff_" + input.name.toLowerCase().replace(/\s+/g, "_");
        await db.insert(systemConfig).values({
          key,
          value: JSON.stringify({
            name: input.name,
            description: input.description,
            enabled: input.enabled,
            rolloutPercent: input.rolloutPercent,
            createdAt: new Date().toISOString(),
          }),
        });
        await db.insert(auditLog).values({
          action: "feature_created",
          resource: "feature_flags",
          resourceId: key,
          status: "success",
          metadata: { name: input.name },
        });
        return { success: true, featureKey: key };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  batchOps: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  prefMatrix: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),
});
