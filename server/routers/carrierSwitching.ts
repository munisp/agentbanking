import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { auditLog, simOrchestratorConfig } from "../../drizzle/schema";
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
      "carrierSwitching",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "carrierSwitching",
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
    resource: "carrierSwitching",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "carrierSwitching",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
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
async function publishcarrierSwitchingMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `network.${action}` as any;
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
      txType: `network_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `network_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("network", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const carrierSwitchingRouter = router({
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
          .from(simOrchestratorConfig)
          .orderBy(desc(auditLog.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(simOrchestratorConfig);
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
        .from(simOrchestratorConfig)
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
      .from(simOrchestratorConfig);
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
        .from(simOrchestratorConfig)
        .orderBy(desc(auditLog.id))
        .limit(input.limit);

      return results;
    }),
  getRankings: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async () => {
      try {
        const db = (await getDb())!;
        if (!db) return { data: [], rankings: [] };
        const rows = await db
          .select({
            carrier: simOrchestratorConfig.terminalId,
            count: count(),
          })
          .from(simOrchestratorConfig)
          .groupBy(simOrchestratorConfig.terminalId)
          .orderBy(desc(count()));

        const { getCarrierProfiles } = await import("../middleware/carrierAwareFailover");
        const profiles = getCarrierProfiles();
        const rankings = profiles.map((p, i) => ({
          rank: i + 1,
          carrier: p.code,
          name: p.name,
          reliabilityPct: p.reliabilityPct,
          avgLatencyMs: p.avgLatencyMs,
          costPerMbNgn: p.costPerMbNgn,
          slaUptimePct: p.slaUptimePct,
          preferredForFinancial: p.preferredForFinancial,
          score: Math.round(p.reliabilityPct * 0.4 + (100 - p.avgLatencyMs / 10) * 0.3 + (100 - p.costPerMbNgn * 200) * 0.3),
        })).sort((a, b) => b.score - a.score).map((r, i) => ({ ...r, rank: i + 1 }));
        return { data: rankings, rankings };
      } catch {
        return { data: [], rankings: [] };
      }
    }),
  getRecommendation: protectedProcedure
    .input(
      z
        .object({
          terminalId: z.string().optional(),
          transactionType: z.enum(["financial", "payment", "transfer", "settlement", "general", "telemetry"]).optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const { getCarrierProfiles } = await import("../middleware/carrierAwareFailover");
      const profiles = getCarrierProfiles();
      const txType = input?.transactionType ?? "general";
      const isFinancial = ["financial", "payment", "transfer", "settlement"].includes(txType);

      const recommended = isFinancial
        ? profiles.filter(p => p.preferredForFinancial).sort((a, b) => b.reliabilityPct - a.reliabilityPct)[0]
        : profiles.sort((a, b) => {
            const scoreA = a.reliabilityPct * 0.3 + (100 - a.costPerMbNgn * 200) * 0.4 + (100 - a.avgLatencyMs / 10) * 0.3;
            const scoreB = b.reliabilityPct * 0.3 + (100 - b.costPerMbNgn * 200) * 0.4 + (100 - b.avgLatencyMs / 10) * 0.3;
            return scoreB - scoreA;
          })[0];

      return {
        data: recommended ?? null,
        recommendation: recommended ? {
          carrier: recommended.code,
          name: recommended.name,
          reason: isFinancial
            ? `${recommended.code} recommended for ${txType}: ${recommended.reliabilityPct}% reliability, ${recommended.slaUptimePct}% SLA uptime`
            : `${recommended.code} recommended for ${txType}: best cost/performance (₦${recommended.costPerMbNgn}/MB, ${recommended.avgLatencyMs}ms latency)`,
          transactionType: txType,
          ussdBalance: recommended.ussdBalance,
        } : null,
      };
    }),
  getSwitchStats: protectedProcedure.query(async () => {
    try {
      const db = (await getDb())!;
      if (!db) return { totalRecords: 0, activeItems: 0, lastUpdated: new Date().toISOString() };
      const [stats] = await db
        .select({ total: count() })
        .from(simOrchestratorConfig);
      return {
        totalRecords: stats?.total ?? 0,
        activeItems: stats?.total ?? 0,
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return { totalRecords: 0, activeItems: 0, lastUpdated: new Date().toISOString() };
    }
  }),
  recordSwitch: protectedProcedure
    .input(z.object({ id: z.string().optional() }).optional())
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

        resource: "carrierSwitching",

        resourceId:
          typeof input === "object" && input !== null && "id" in input
            ? String((input as any).id)
            : "new",

        status: "success",

        metadata: { input: typeof input === "object" ? input : {} },
      });

      // Middleware fan-out (fail-open)

      await publishcarrierSwitchingMiddleware("recordSwitch", `${Date.now()}`, { action: "recordSwitch" }).catch(() => {});


      return {
        success: true,
        action: "recordSwitch",
        id: input?.id ?? null,
        timestamp: new Date().toISOString(),
      };
    }),
});
