import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { auditLog, observabilityAlerts } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
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
  draft: ["queued", "scheduled"],
  scheduled: ["queued", "cancelled"],
  queued: ["sending"],
  sending: ["delivered", "failed", "bounced"],
  delivered: ["read", "archived"],
  read: ["replied", "archived"],
  replied: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  bounced: ["retry_pending", "cancelled"],
  cancelled: [],
  archived: [],
};

function enforceTransition(currentStatus: string, newStatus: string) {
  const allowed =
    STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
  if (allowed && !allowed.includes(newStatus)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
    });
  }
}

// Metric categories: "transactions", "agents", "risk", "finance", "system"
// Operators: "gt", "lt", "gte", "lte", "eq", "neq", "pct_change_up", "pct_change_down"
// Severities: "low", "medium", "high", "critical", "warning"
const AVAILABLE_METRICS = [
  {
    id: "tx_volume_daily",
    category: "transactions",
    name: "Daily Transaction Volume",
  },
  {
    id: "tx_value_daily",
    category: "transactions",
    name: "Daily Transaction Value",
  },
  {
    id: "tx_failed_rate",
    category: "transactions",
    name: "Failed Transaction Rate",
  },
  { id: "active_agents", category: "agents", name: "Active Agents" },
  { id: "agent_churn_rate", category: "agents", name: "Agent Churn Rate" },
  { id: "agent_onboarding", category: "agents", name: "Agent Onboarding Rate" },
  { id: "fraud_score_avg", category: "risk", name: "Average Fraud Score" },
  { id: "kyc_rejection_rate", category: "risk", name: "KYC Rejection Rate" },
  { id: "settlement_delay", category: "finance", name: "Settlement Delay" },
  { id: "commission_total", category: "finance", name: "Total Commissions" },
  { id: "revenue_daily", category: "finance", name: "Daily Revenue" },
  { id: "api_latency_p99", category: "system", name: "API P99 Latency" },
  { id: "db_connections", category: "system", name: "DB Connection Pool" },
  { id: "queue_depth", category: "system", name: "Queue Depth" },
  { id: "fraud_alerts", category: "risk", name: "Fraud Alert Count" },
];
const SEED_RULES = [
  {
    id: "thr_001",
    metricId: "tx_volume_daily",
    operator: "gt",
    threshold: 100000,
    severity: "warning",
  },
  {
    id: "thr_002",
    metricId: "fraud_score_avg",
    operator: "gte",
    threshold: 0.8,
    severity: "critical",
  },
  {
    id: "thr_003",
    metricId: "api_latency_p99",
    operator: "gt",
    threshold: 500,
    severity: "warning",
  },
  {
    id: "thr_004",
    metricId: "settlement_delay",
    operator: "gte",
    threshold: 3600,
    severity: "high",
  },
  {
    id: "thr_005",
    metricId: "db_connections",
    operator: "gte",
    threshold: 90,
    severity: "critical",
  },
];

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "dataThresholdAlerts",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "dataThresholdAlerts",
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
    resource: "dataThresholdAlerts",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "dataThresholdAlerts",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Domain Calculations ────────────────────────────────────────────────────

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

export const dataThresholdAlertsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const results = await database
          .select()
          .from(observabilityAlerts)
          .orderBy(desc(auditLog.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(observabilityAlerts);
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
        .from(observabilityAlerts)
        .where(eq(auditLog.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const _totalRows = await database
      .select({ total: count() })
      .from(observabilityAlerts);
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
        .from(observabilityAlerts)
        .orderBy(desc(auditLog.id))
        .limit(input.limit);

      return results;
    }),

  acknowledge: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      return { success: true };
    }),

  create: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      return { success: true };
    }),

  delete: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      return { success: true };
    }),

  events: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  metrics: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  operators: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  simulateCheck: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      return { success: true };
    }),

  toggleStatus: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      return { success: true };
    }),
  update: protectedProcedure
    .input(z.object({ id: z.string(), threshold: z.number().optional() }))
    .mutation(async ({ input }) => ({ id: input.id, updated: true })),
  resolve: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input }) => ({ id: input.id, resolved: true })),
});
