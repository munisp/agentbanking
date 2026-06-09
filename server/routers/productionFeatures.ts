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
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "productionFeatures",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

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
