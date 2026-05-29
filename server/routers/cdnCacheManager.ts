import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import {
  getCacheMetrics,
  invalidateCache,
  invalidateCacheByPrefix,
} from "../lib/cacheAside";
import { redisIsHealthy } from "../redisClient";
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

export const cdnCacheManagerRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().optional(),
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
    .input(z.object({ zoneId: z.string(), pattern: z.string().optional() }))
    .mutation(async ({ input }) => {
      const key = input.pattern
        ? `${input.zoneId}:${input.pattern}`
        : input.zoneId;
      const count = await invalidateCache(key);
      return {
        success: true,
        zoneId: input.zoneId,
        purgedKeys: count,
        timestamp: new Date().toISOString(),
      };
    }),

  purgeAll: protectedProcedure.mutation(async () => {
    const count = await invalidateCacheByPrefix("trpc:");
    return {
      success: true,
      purgedKeys: count,
      timestamp: new Date().toISOString(),
    };
  }),
});
