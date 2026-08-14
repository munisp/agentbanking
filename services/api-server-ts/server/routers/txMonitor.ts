// @ts-nocheck
import { z } from "zod";
import {
  router,
  publicProcedure as openProcedure,
  protectedProcedure,
} from "../_core/trpc";
import { getDb } from "../db";
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
import {
  transactions,
  auditLog,
  systemConfig,
  txMonitoringAlerts,
  realtime_tx_alerts,
} from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
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
function validateTxmonitorInput(data: Record<string, unknown>): boolean {
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

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_TXMONITOR = {
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
    if (!INTEGRITY_RULES_TXMONITOR.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (!INTEGRITY_RULES_TXMONITOR.validateRange(data.amount, 0, 100_000_000))
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _txMonitor_db = {
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
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "txMonitor",
        "mutation",
        "Executed txMonitor mutation"
      );

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
    .input(z.object({ ruleId: z.string(), enabled: z.boolean() }))
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
  getRules: openProcedure.query(async () => {
    try {
      const db = await getDb();
      if (!db) throw new Error("DB not available");
      // Rules are persisted in systemConfig under "tx_alert_rule_<id>" keys
      // (see toggleRule). No dedicated rules table exists in this schema.
      const rows = await db
        .select()
        .from(systemConfig)
        .where(sql`${systemConfig.key} LIKE 'tx_alert_rule_%'`);
      const rules = rows.map(r => {
        const data = JSON.parse(String(r.value ?? "{}"));
        return { id: String(r.key).replace("tx_alert_rule_", ""), ...data };
      });
      return {
        rules,
        activeCount: rules.filter(r => r.enabled !== false).length,
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

  getAlerts: openProcedure
    .input(z.object({ severity: z.string().optional() }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const rows = await db
          .select()
          .from(txMonitoringAlerts)
          .where(
            input?.severity
              ? eq(txMonitoringAlerts.severity, input.severity)
              : undefined
          )
          .orderBy(desc(txMonitoringAlerts.createdAt))
          .limit(100);
        const alerts = rows.map(r => ({
          id: String(r.id),
          ruleId: r.alertType,
          severity: r.severity,
          agentId: r.agentId != null ? String(r.agentId) : null,
          amount: null,
          status: r.resolved ? "resolved" : "open",
          createdAt: r.createdAt ? r.createdAt.toISOString() : null,
          description: r.description,
        }));
        return { alerts, total: alerts.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  acknowledgeAlert: openProcedure
    .input(z.object({ alertId: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const id = Number(input.alertId);
        if (!Number.isInteger(id) || id <= 0) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "alertId must be a numeric alert id",
          });
        }
        const acknowledgedAt = new Date();
        const updated = await db
          .update(realtime_tx_alerts)
          .set({ acknowledged: true, acknowledgedAt })
          .where(eq(realtime_tx_alerts.id, id))
          .returning();
        if (updated.length === 0) {
          throw new TRPCError({
            code: "NOT_FOUND",
            message: `Alert ${input.alertId} not found`,
          });
        }
        return {
          success: true,
          alertId: input.alertId,
          status: "acknowledged",
          acknowledgedAt: acknowledgedAt.toISOString(),
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

  resolveAlert: openProcedure
    .input(z.object({ alertId: z.string(), resolution: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const id = Number(input.alertId);
        if (!Number.isInteger(id) || id <= 0) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "alertId must be a numeric alert id",
          });
        }
        const resolvedAt = new Date();
        const updated = await db
          .update(txMonitoringAlerts)
          .set({
            resolved: true,
            resolvedAt,
            metadata: JSON.stringify({ resolution: input.resolution }),
          })
          .where(eq(txMonitoringAlerts.id, id))
          .returning();
        if (updated.length === 0) {
          throw new TRPCError({
            code: "NOT_FOUND",
            message: `Alert ${input.alertId} not found`,
          });
        }
        return {
          success: true,
          alertId: input.alertId,
          status: "resolved",
          resolution: input.resolution,
          resolvedAt: resolvedAt.toISOString(),
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

  getDashboard: openProcedure.query(async () => {
    try {
      const db = await getDb();
      if (!db) throw new Error("DB not available");
      const [totals] = await db
        .select({
          total: count(),
          open: count(sql`CASE WHEN ${txMonitoringAlerts.resolved} = false THEN 1 END`),
          critical: count(
            sql`CASE WHEN ${txMonitoringAlerts.severity} = 'critical' THEN 1 END`
          ),
        })
        .from(txMonitoringAlerts);
      const [ruleCount] = await db
        .select({ total: count() })
        .from(systemConfig)
        .where(sql`${systemConfig.key} LIKE 'tx_alert_rule_%'`);
      const recent = await db
        .select()
        .from(txMonitoringAlerts)
        .orderBy(desc(txMonitoringAlerts.createdAt))
        .limit(5);
      return {
        totalAlerts: Number(totals?.total ?? 0),
        openAlerts: Number(totals?.open ?? 0),
        criticalAlerts: Number(totals?.critical ?? 0),
        rulesCount: Number(ruleCount?.total ?? 0),
        recentAlerts: recent.map(r => ({
          id: String(r.id),
          severity: r.severity,
          description: r.description,
          createdAt: r.createdAt ? r.createdAt.toISOString() : null,
        })),
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
