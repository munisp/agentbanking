/**
 * tRPC caching middleware — automatic query result caching via Redis.
 *
 * Read-through cache for query (read) procedures:
 *   1. BEFORE next(): cacheGet — on hit, short-circuit with the cached payload.
 *   2. AFTER next(): cacheSet successful results (fire-and-forget).
 * Mutations and subscriptions bypass the cache entirely.
 *
 * Cache key format: trpc:{userId}:{path}:{hash(serializedInput)}
 *   The user id is part of the key so one user's cached results can never be
 *   served to another user. Anonymous callers share the "anon" bucket, which
 *   only ever contains results produced by genuinely public procedures
 *   (protected procedures always run with ctx.user set by createContext).
 *
 * TTL: 10s default (PATH_TTL overrides per path). Staleness bound: a revoked
 * permission or updated record may be served from cache for at most the TTL.
 *
 * Fail-open: any Redis error (both helpers already swallow errors and return
 * null/false) results in a normal uncached call — the cache never blocks or
 * breaks the request path.
 *
 * Serialization: superjson (the configured tRPC transformer) so Dates/Maps in
 * resolver results round-trip correctly through the cache.
 */

import { cacheGet, cacheSet } from "../redisClient";
import crypto from "crypto";
import superjson from "superjson";

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

const DEFAULT_TTL = 10;

function hashInput(input: unknown): string {
  if (input === undefined || input === null) return "no-input";
  return crypto
    .createHash("md5")
    .update(superjson.stringify(input))
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
      ctx?: { user?: { id?: number | string } | null };
    }) => {
      const { path, type, next } = opts;

      // Only cache queries, skip mutations/subscriptions
      if (type !== "query") return next();
      if (SKIP_CACHE_PATHS.has(path)) return next();

      const userId = opts.ctx?.user?.id != null ? String(opts.ctx.user.id) : "anon";
      const cacheKey = `trpc:${userId}:${path}:${hashInput(opts.rawInput)}`;
      const ttl = PATH_TTL[path] ?? DEFAULT_TTL;

      // 1. Read-through: serve from Redis on hit. cacheGet returns null on any
      //    Redis error, so failures fall through to a normal procedure call.
      const cached = await cacheGet(cacheKey);
      if (cached !== null) {
        try {
          return { ok: true, data: superjson.parse(cached) };
        } catch {
          // Corrupt/legacy payload — treat as a miss and overwrite below.
        }
      }

      // 2. Execute the procedure
      const result = await next();

      // Cache successful results in Redis (fire-and-forget)
      if (result.ok) {
        try {
          cacheSet(cacheKey, superjson.stringify(result.data), ttl).catch(
            () => {}
          );
        } catch {
          // superjson.stringify on unserializable data must not break the call
        }
      }

      return result;
    }
  );
}
