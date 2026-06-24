/**
 * systemConfig router
 *
 * Admin-settable key-value configuration store backed by the system_config table.
 * Provides:
 *   - getSystemConfig: read one or all config values (protected procedure)
 *   - setSystemConfig: write a config value (admin-only)
 *   - listSystemConfig: list all config entries (admin-only)
 *
 * Default seeds (applied at first migration):
 *   dead_letter_auto_retry_threshold = "5"
 *   alert_throttle_window_minutes    = "30"
 */

import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { systemConfig } from "../../drizzle/schema";
import { eq, and, gte, lte, desc, sql, count } from "drizzle-orm";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

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
      "systemConfig",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "systemConfig",
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
    resource: "systemConfig",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "systemConfig",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Database Operations Helper ─────────────────────────────────────────────
async function checkDbHealth() {
  try {
    const db = await (await import("../db")).getDb();
    if ((db as any)?._isNoop) return { connected: false, latencyMs: 0 };
    const start = Date.now();
    await db
      .select({ val: (await import("drizzle-orm")).sql`1` })
      .from((await import("drizzle-orm")).sql`(SELECT 1) AS t`);
    return { connected: true, latencyMs: Date.now() - start };
  } catch {
    return { connected: false, latencyMs: 0 };
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


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishsystemConfigMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `platform.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(() => {});

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `platform_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `platform_${action}`,
    timestamp: ts,
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("platform", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const systemConfigRouter = router({
  // ── Get a single config value by key ─────────────────────────────────────
  get: protectedProcedure
    .input(z.object({ key: z.string().min(1).max(128) }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { key: input.key, value: null };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, input.key))
          .limit(1);
        if (rows.length === 0) return { key: input.key, value: null };
        return {
          key: rows[0].key,
          value: rows[0].value,
          description: rows[0].description,
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

  // ── List all config entries (admin-only) ─────────────────────────────────
  list: protectedProcedure.query(async ({ ctx }) => {
    try {
      if (ctx.user.role !== "admin" && ctx.user.role !== "supervisor") {
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "Admin access required",
        });
      }
      const db = (await getDb())!;
      if (!db) return { entries: [] };
      const rows = await db
        .select()
        .from(systemConfig)
        .orderBy(systemConfig.key)
        .limit(100);
      return { entries: rows };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),

  // ── Set a config value (admin-only) ──────────────────────────────────────
  set: protectedProcedure
    .input(
      z.object({
        key: z.string().min(1).max(128),
        value: z.string().max(4096),
        description: z.string().max(512).optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
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
        if (ctx.user.role !== "admin" && ctx.user.role !== "supervisor") {
          throw new TRPCError({
            code: "FORBIDDEN",
            message: "Admin access required",
          });
        }
        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        const now = new Date();
        const updatedBy = ctx.user.name ?? ctx.user.email ?? "unknown";

        // Upsert: insert if not exists, update if exists
        await db
          .insert(systemConfig)
          .values({
            key: input.key,
            value: input.value,
            description: input.description,
            updatedBy,
            createdAt: now,
            updatedAt: now,
          })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: {
              value: input.value,
              description: input.description ?? undefined,
              updatedBy,
              updatedAt: now,
            },
          });

        // Middleware fan-out (fail-open)

        await publishSystemConfigMiddleware("set", `${Date.now()}`, { action: "set" }).catch(() => {});


        return {
          key: input.key,
          value: input.value,
          updatedBy,
          updatedAt: now,
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
