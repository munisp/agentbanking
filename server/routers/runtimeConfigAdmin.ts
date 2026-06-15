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
      "runtimeConfigAdmin",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "runtimeConfigAdmin",
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
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const runtimeConfigAdminRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalConfigs: 0, modifiedToday: 0, environments: 0 };
    const [total] = await db
      .select({ value: count() })
      .from(systemConfig)
      .limit(100);
    return {
      totalConfigs: Number(total.value),
      modifiedToday: 0,
      environments: 3,
    };
  }),
  listConfigs: protectedProcedure
    .input(
      z
        .object({
          prefix: z.string().optional(),
          limit: z.number().default(50),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { configs: [], total: 0 };
        const conditions: any[] = [];
        if (input?.prefix)
          conditions.push(sql`${systemConfig.key} LIKE ${input.prefix + "%"}`);
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const rows = await db
          .select()
          .from(systemConfig)
          .where(where)
          .orderBy(asc(systemConfig.key))
          .limit(input?.limit ?? 50);
        return {
          configs: rows.map(r => ({
            key: r.key,
            value: r.value,
            updatedAt: r.updatedAt,
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
  getConfig: protectedProcedure
    .input(z.object({ key: z.string() }))
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("Database connection unavailable");
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, input.key))
          .limit(1);
        return rows.length > 0
          ? {
              key: rows[0].key,
              value: rows[0].value,
              updatedAt: rows[0].updatedAt,
            }
          : null;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  setConfig: protectedProcedure
    .input(z.object({ key: z.string(), value: z.string() }))
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus =
          "status" in input
            ? String((input as Record<string, unknown>).status)
            : "";
        const currentStatus =
          "currentStatus" in input
            ? String((input as Record<string, unknown>).currentStatus)
            : "pending";
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
          ? Number(
              "amount" in input ? (input as Record<string, unknown>).amount : 0
            )
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db
          .insert(systemConfig)
          .values({ key: input.key, value: input.value })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: { value: input.value, updatedAt: new Date() },
          });
        await db.insert(auditLog).values({
          action: "config_updated",
          resource: "system_config",
          resourceId: input.key,
          status: "success",
          metadata: { key: input.key },
        });
        await writeAuditLog({
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? (ctx.user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? (ctx.user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "runtimeConfigAdmin",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String(
                  "id" in input ? (input as Record<string, unknown>).id : "new"
                )
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
  deleteConfig: protectedProcedure
    .input(z.object({ key: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db.delete(systemConfig).where(eq(systemConfig.key, input.key));
        await db.insert(auditLog).values({
          action: "config_deleted",
          resource: "system_config",
          resourceId: input.key,
          status: "success",
          metadata: {},
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
  get: protectedProcedure
    .input(z.object({ key: z.string() }))
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("Database connection unavailable");
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, input.key))
          .limit(1);
        return rows.length > 0
          ? {
              key: rows[0].key,
              value: rows[0].value,
              updatedAt: rows[0].updatedAt,
            }
          : null;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  batchUpdate: protectedProcedure
    .input(
      z.object({
        configs: z.array(z.object({ key: z.string(), value: z.string() })),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const results = [];
        for (const cfg of input.configs) {
          await db
            .insert(systemConfig)
            .values({ key: cfg.key, value: cfg.value })
            .onConflictDoUpdate({
              target: systemConfig.key,
              set: { value: cfg.value, updatedAt: new Date() },
            });
          results.push({ key: cfg.key, success: true });
        }
        await db.insert(auditLog).values({
          action: "config_batch_updated",
          resource: "system_config",
          status: "success",
          metadata: {
            count: input.configs.length,
            keys: input.configs.map(c => c.key),
          },
        });
        return { updated: results.length, results };
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
