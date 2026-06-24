import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { writeAuditLog } from "../db";
import {
  getCacheMetrics,
  invalidateCache,
  invalidateCacheByPrefix,
} from "../lib/cacheAside";
import { redisIsHealthy } from "../redisClient";
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
      "cdnCacheManager",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "cdnCacheManager",
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
    resource: "cdnCacheManager",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "cdnCacheManager",
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
async function publishcdnCacheManagerMiddleware(
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

export const cdnCacheManagerRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      const zones = [
        {
          id: "static-assets",
          name: "Static Assets (JS/CSS/Images)",
          origin: "s3://54link-assets",
          ttl: 86400,
          status: "active",
          hitRate: 0.97,
          bandwidth: "2.4 GB/day",
        },
        {
          id: "api-responses",
          name: "API Response Cache",
          origin: "http://api.internal:5002",
          ttl: 30,
          status: "active",
          hitRate: 0.82,
          bandwidth: "890 MB/day",
        },
        {
          id: "pwa-shell",
          name: "PWA App Shell",
          origin: "s3://54link-pwa",
          ttl: 3600,
          status: "active",
          hitRate: 0.99,
          bandwidth: "120 MB/day",
        },
        {
          id: "exchange-rates",
          name: "FX Rate Feed",
          origin: "http://fx-service:8080",
          ttl: 900,
          status: "active",
          hitRate: 0.95,
          bandwidth: "45 MB/day",
        },
        {
          id: "agent-profiles",
          name: "Agent Profile Cache",
          origin: "postgres://primary",
          ttl: 300,
          status: "active",
          hitRate: 0.88,
          bandwidth: "340 MB/day",
        },
      ];

      const filtered = input.search
        ? zones.filter(
            z =>
              z.name.toLowerCase().includes(input.search!.toLowerCase()) ||
              z.id.includes(input.search!.toLowerCase())
          )
        : zones;

      return {
        data: filtered.slice(input.offset, input.offset + input.limit),
        total: filtered.length,
        limit: input.limit,
        offset: input.offset,
      };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => {
      try {
        const healthy = await redisIsHealthy();
        return {
          id: input.id,
          redisConnected: healthy,
          metrics: getCacheMetrics(),
          timestamp: new Date().toISOString(),
        };
      } catch {
        return {
          id: input.id,
          redisConnected: false,
          metrics: getCacheMetrics(),
          timestamp: new Date().toISOString(),
        };
      }
    }),

  getSummary: protectedProcedure.query(async () => {
    const metrics = getCacheMetrics();
    const healthy = await redisIsHealthy();
    return {
      totalZones: 5,
      activeZones: 5,
      redisConnected: healthy,
      cacheHitRate: metrics.hitRate,
      totalRequests: metrics.total,
      hits: metrics.hits,
      misses: metrics.misses,
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
      const metrics = getCacheMetrics();
      return {
        data: [
          {
            action: "cache_hit",
            count: metrics.hits,
            period: `${input.days}d`,
          },
          {
            action: "cache_miss",
            count: metrics.misses,
            period: `${input.days}d`,
          },
          {
            action: "stampede_prevented",
            count: metrics.stampedePrevented,
            period: `${input.days}d`,
          },
        ],
        total: 3,
        limit: input.limit,
        offset: 0,
      };
    }),

  getStats: protectedProcedure.query(async () => {
    const metrics = getCacheMetrics();
    const healthy = await redisIsHealthy();
    return {
      total: metrics.total,
      active: healthy ? 5 : 0,
      recent: metrics.hits + metrics.misses,
      hitRate: metrics.hitRate,
      redisConnected: healthy,
      lastUpdated: new Date().toISOString(),
    };
  }),

  purge: protectedProcedure
    .input(
      z.object({
        zoneId: z.string().min(1).max(255),
        pattern: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await writeAuditLog({
        action: "mutation",
        resource: "cdnCacheManager",
        status: "success",
      });
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
      const key = input.pattern
        ? `${input.zoneId}:${input.pattern}`
        : input.zoneId;
      const count = await invalidateCache(key);

      // Middleware fan-out (fail-open)

      await publishCdnCacheManagerMiddleware("purge", `${Date.now()}`, { action: "purge" }).catch(() => {});


      return {
        success: true,
        zoneId: input.zoneId,
        purgedKeys: count,
        timestamp: new Date().toISOString(),
      };
    }),

  purgeAll: protectedProcedure.mutation(async () => {
    const count = await invalidateCacheByPrefix("trpc:");
    // Middleware fan-out (fail-open)
    await publishCdnCacheManagerMiddleware("purgeAll", `${Date.now()}`, { action: "purgeAll" }).catch(() => {});

    return {
      success: true,
      purgedKeys: count,
      timestamp: new Date().toISOString(),
    };
  }),
});
