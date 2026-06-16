/**
 * tRPC caching middleware — automatic query result caching via Redis.
 *
 * Caches all query (read) procedure results with configurable TTL.
 * Mutations bypass the cache entirely.
 *
 * Cache key format: trpc:{path}:{hash(input)}
 * Default TTL: 30s for most queries, configurable per-path.
 */

import { cacheSet } from "../redisClient";
import crypto from "crypto";

const PATH_TTL: Record<string, number> = {
  "healthCheck.status": 10,
  "healthCheck.dbHealth": 15,
  "healthCheck.middlewareHealth": 30,
  "cache.getStats": 5,
  "cache.list": 30,
  "dashboard.getSummary": 30,
  "dashboard.getStats": 30,
  "analytics.getSummary": 60,
  "analytics.getOverview": 60,
  "agentPerformance.getStats": 45,
  "agentPerformance.getSummary": 45,
  "exchangeRates.getLatest": 900,
  "systemConfig.getAll": 300,
  "platformSettings.list": 120,
};

const SKIP_CACHE_PATHS = new Set([
  "auth.me",
  "auth.login",
  "auth.logout",
  "auth.register",
]);

const DEFAULT_TTL = 30;

function hashInput(input: unknown): string {
  if (input === undefined || input === null) return "no-input";
  return crypto
    .createHash("md5")
    .update(JSON.stringify(input))
    .digest("hex")
    .slice(0, 12);
}

export function createTrpcCacheMiddleware(t: { middleware: (fn: any) => any }) {
  return t.middleware(
    async (opts: {
      path: string;
      type: string;
      next: () => Promise<any>;
      rawInput?: unknown;
    }) => {
      const { path, type, next } = opts;

      // Only cache queries, skip mutations/subscriptions
      if (type !== "query") return next();
      if (SKIP_CACHE_PATHS.has(path)) return next();

      // Execute the procedure
      const result = await next();

      // Cache successful results in Redis (fire-and-forget)
      if (result.ok) {
        const inputHash = hashInput(opts.rawInput);
        const cacheKey = `trpc:${path}:${inputHash}`;
        const ttl = PATH_TTL[path] ?? DEFAULT_TTL;
        cacheSet(cacheKey, JSON.stringify(result.data), ttl).catch(() => {});
      }

      return result;
    }
  );
}
