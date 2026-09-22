/**
 * Cache-aside (read-through) wrapper for Redis caching.
 *
 * Usage:
 *   const data = await withCache('user:123', 300, () => db.query(...));
 *
 * Features:
 *  - Generic cache-aside pattern with configurable TTL
 *  - Singleflight / stampede protection (dedup concurrent requests for same key)
 *  - ETag generation for conditional HTTP responses
 *  - Fail-open: returns fresh data if Redis is unavailable
 *  - Metrics tracking (hits, misses, errors)
 */

import { cacheGet, cacheSet, cacheDel, cachePublish } from "../redisClient";
import crypto from "crypto";
import superjson from "superjson";

const inflight = new Map<string, Promise<unknown>>();

const metrics = {
  hits: 0,
  misses: 0,
  errors: 0,
  stampedePrevented: 0,
};

export function getCacheMetrics() {
  const total = metrics.hits + metrics.misses;
  return {
    ...metrics,
    total,
    hitRate: total > 0 ? metrics.hits / total : 0,
  };
}

export async function withCache<T>(
  key: string,
  ttlSeconds: number,
  fetchFn: () => Promise<T>
): Promise<T> {
  // Check Redis first
  try {
    const cached = await cacheGet(key);
    if (cached !== null) {
      metrics.hits++;
      return JSON.parse(cached) as T;
    }
  } catch {
    metrics.errors++;
  }

  metrics.misses++;

  // Stampede protection: if another caller is already fetching this key, wait for it
  const existing = inflight.get(key);
  if (existing) {
    metrics.stampedePrevented++;
    return existing as Promise<T>;
  }

  const promise = fetchFn()
    .then(async result => {
      // Store in Redis
      try {
        await cacheSet(key, JSON.stringify(result), ttlSeconds);
      } catch {
        // fail-open
      }
      inflight.delete(key);
      return result;
    })
    .catch(err => {
      inflight.delete(key);
      throw err;
    });

  inflight.set(key, promise);
  return promise;
}

/**
 * withCacheTyped — same cache-aside + singleflight pattern as withCache, but
 * serializes with superjson so Date/Map/undefined fields in Drizzle row
 * objects round-trip correctly (withCache's JSON.stringify turns Dates into
 * strings, which breaks callers that treat them as Date instances).
 *
 * Round-8 usage: hot identity lookups (session user, agent row) with a short
 * 15s TTL. No invalidation hooks exist on the user/agent write paths, so the
 * staleness bound IS the TTL: a suspended/updated principal may be served a
 * stale row for up to 15s. Do NOT raise the TTL without adding invalidation.
 */
export async function withCacheTyped<T>(
  key: string,
  ttlSeconds: number,
  fetchFn: () => Promise<T>
): Promise<T> {
  try {
    const cached = await cacheGet(key);
    if (cached !== null) {
      metrics.hits++;
      return superjson.parse(cached) as T;
    }
  } catch {
    metrics.errors++;
  }

  metrics.misses++;

  const existing = inflight.get(key);
  if (existing) {
    metrics.stampedePrevented++;
    return existing as Promise<T>;
  }

  const promise = fetchFn()
    .then(async result => {
      try {
        // Only cache defined results — misses/errors are never cached.
        if (result !== undefined && result !== null) {
          await cacheSet(key, superjson.stringify(result), ttlSeconds);
        }
      } catch {
        // fail-open
      }
      inflight.delete(key);
      return result;
    })
    .catch(err => {
      inflight.delete(key);
      throw err;
    });

  inflight.set(key, promise);
  return promise;
}

export function generateETag(data: unknown): string {
  const hash = crypto
    .createHash("md5")
    .update(JSON.stringify(data))
    .digest("hex");
  return `"${hash}"`;
}

export async function invalidateCache(pattern: string): Promise<number> {
  try {
    await cacheDel(pattern);
    await cachePublish("cache:invalidate", pattern);
    return 1;
  } catch {
    return 0;
  }
}

export async function invalidateCacheByPrefix(prefix: string): Promise<number> {
  try {
    await cachePublish("cache:invalidate:prefix", prefix);
    return 1;
  } catch {
    return 0;
  }
}
