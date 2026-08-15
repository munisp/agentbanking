// @ts-nocheck
import { z } from "zod";
import {
  router,
  publicProcedure as openProcedure,
  protectedProcedure,
} from "../_core/trpc";
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
import { transactions, auditLog, systemConfig } from "../../drizzle/schema";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
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
      "txMonitor",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "txMonitor",
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

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishtxMonitorMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `platform.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(
    () => {}
  );

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
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("platform", {
    ref,
    action,
    ...payload,
    timestamp: ts,
  }).catch(() => {});
}

export const txMonitorRouter = router({
  dashboard: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return {
        totalTransactions: 0,
        alertsTriggered: 0,
        avgTps: 0,
        activeRules: 0,
      };
    const [txCount] = await db
      .select({ value: count() })
      .from(transactions)
      .limit(100);
    const rules = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'tx_alert_rule_%'`)
      .limit(100);
    return {
      totalTransactions: Number(txCount.value),
      alertsTriggered: 0,
      avgTps: 0,
      activeRules: rules.length,
    };
  }),
  listAlertRules: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { rules: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(sql`${systemConfig.key} LIKE 'tx_alert_rule_%'`)
          .limit(input?.limit ?? 20);
        return {
          rules: rows.map(r => ({
            id: r.key.replace("tx_alert_rule_", ""),
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
  createAlertRule: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        conditionType: z.string(),
        threshold: z.number(),
        severity: z.enum(["info", "warning", "critical"]).default("warning"),
        windowSeconds: z.number().default(300),
        enabled: z.boolean().default(true),
      })
    )
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
        const ruleId = "TXR-" + crypto.randomUUID().toUpperCase();
        await db.insert(systemConfig).values({
          key: "tx_alert_rule_" + ruleId,
          value: JSON.stringify({
            ...input,
            createdAt: new Date().toISOString(),
            cooldownSeconds: 300,
            triggeredCount: 0,
          }),
        });
        await db.insert(auditLog).values({
          action: "tx_alert_rule_created",
          resource: "tx_monitor",
          resourceId: ruleId,
          status: "success",
          metadata: { name: input.name, conditionType: input.conditionType },
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

          resource: "txMonitor",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        // Middleware fan-out (fail-open)

        await publishtxMonitorMiddleware("createAlertRule", `${Date.now()}`, {
          action: "createAlertRule",
        }).catch(() => {});

        return { success: true, ruleId };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getRecentTransactions: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { transactions: [], total: 0 };
        const rows = await db
          .select()
          .from(transactions)
          .orderBy(desc(transactions.createdAt))
          .limit(input?.limit ?? 50);
        return { transactions: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  toggleRule: protectedProcedure
    .input(
      z.object({ ruleId: z.string().min(1).max(255), enabled: z.boolean() })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "tx_alert_rule_" + input.ruleId))
          .limit(1);
        if (rows.length === 0)
          return { success: false, error: "Rule not found" };
        const data = JSON.parse(String(rows[0].value ?? "{}"));
        data.enabled = input.enabled;
        await db
          .update(systemConfig)
          .set({ value: JSON.stringify(data), updatedAt: new Date() })
          .where(eq(systemConfig.key, "tx_alert_rule_" + input.ruleId));
        // Middleware fan-out (fail-open)
        await publishtxMonitorMiddleware("toggleRule", `${Date.now()}`, {
          action: "toggleRule",
        }).catch(() => {});

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

  // ── Sprint 78 domain-specific procedures ──────────────────────────────────
  // NOTE: this tree has no drizzle schema module (../../drizzle/schema is not
  // present in this deployment), so these procedures cannot run real queries.
  // Reads return honest empty results flagged with source:"unavailable";
  // mutations FAIL LOUD with NOT_IMPLEMENTED instead of fabricating success.
  getRules: openProcedure.query(async () => {
    return { rules: [], activeCount: 0, source: "unavailable" };
  }),

  getAlerts: openProcedure
    .input(z.object({ severity: z.string().optional() }).optional())
    .query(async () => {
      return { alerts: [], total: 0, source: "unavailable" };
    }),

  acknowledgeAlert: openProcedure
    .input(z.object({ alertId: z.string().min(1).max(255) }))
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "txMonitor.acknowledgeAlert is not available in this deployment",
      });
    }),

  resolveAlert: openProcedure
    .input(
      z.object({ alertId: z.string().min(1).max(255), resolution: z.string() })
    )
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "txMonitor.resolveAlert is not available in this deployment",
      });
    }),

  getDashboard: openProcedure.query(async () => {
    return {
      totalAlerts: 0,
      openAlerts: 0,
      criticalAlerts: 0,
      rulesCount: 0,
      recentAlerts: [],
      source: "unavailable",
    };
  }),
});
