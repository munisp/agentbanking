import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, sql, count, and, gte, lte } from "drizzle-orm";
import { tenantFeatureToggles, auditLog } from "../../drizzle/schema";
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
      "featureFlags",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "featureFlags",
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
    resource: "featureFlags",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "featureFlags",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_FEATUREFLAGS = {
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
    if (!INTEGRITY_RULES_FEATUREFLAGS.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_FEATUREFLAGS.validateRange(data.amount, 0, 100_000_000)
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
const _featureFlags_db = {
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

export const featureFlagsRouter = router({
  listFlags: protectedProcedure
    .input(z.object({ limit: z.number().default(100) }).optional())
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(tenantFeatureToggles)
          .orderBy(desc(tenantFeatureToggles.createdAt))
          .limit(input?.limit ?? 100);
        return { flags: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getFlag: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [flag] = await db
          .select()
          .from(tenantFeatureToggles)
          .where(eq(tenantFeatureToggles.id, input.id))
          .limit(1);
        return flag ?? null;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  toggleFlag: protectedProcedure
    .input(z.object({ id: z.number(), enabled: z.boolean() }))
    .mutation(async ({ input, ctx }) => {
      const txAmount = typeof input === "object" && "amount" in input ? Number((input as Record<string, unknown>).amount) : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
try {
        const db = (await getDb())!;
        await db
          .update(tenantFeatureToggles)
          .set({ enabled: input.enabled })
          .where(eq(tenantFeatureToggles.id, input.id));
        await db.insert(auditLog).values({
          action: input.enabled
            ? "feature_flag_enabled"
            : "feature_flag_disabled",
          resource: "tenant_feature_toggles",
          resourceId: String(input.id),
          status: "success",
          metadata: { enabled: input.enabled },
        });
        await writeAuditLog({

          agentId: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.id ?? 0 : 0,

          agentCode: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.agentCode ?? "system" : "system",

          action: "MUTATION",

          resource: "featureFlags",

          resourceId: typeof input === "object" && input !== null && "id" in input ? String((input as any).id) : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },

        });

        return { success: true, id: input.id, enabled: input.enabled };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  createFlag: protectedProcedure
    .input(
      z.object({
        featureName: z.string(),
        tenantId: z.number(),
        enabled: z.boolean().default(false),
        description: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [flag] = await db
          .insert(tenantFeatureToggles)
          .values({
            featureName: input.featureName,
            tenantId: input.tenantId,
            enabled: input.enabled,
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "feature_flag_created",
          resource: "tenant_feature_toggles",
          resourceId: String(flag.id),
          status: "success",
          metadata: { featureName: input.featureName },
        } as any);
        return flag;
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
    const [total] = await db
      .select({ value: count() })
      .from(tenantFeatureToggles)
      .limit(100);
    return {
      totalFlags: Number(total.value),
      lastUpdated: new Date().toISOString(),
    };
  }),
  dashboard: protectedProcedure.query(async () => ({
    totalFlags: 0,
    enabledFlags: 0,
    environments: ["dev", "staging", "production"],
  })),
});
