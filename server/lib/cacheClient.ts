/**
 * Cache Client (Redis wrapper)
 * Provides get/set/invalidate with TTL. Fail-open on Redis unavailability.
 * Re-exports from redisClient for backward compatibility.
 */

import { cacheGet as redisGet, cacheSet as redisSet } from "../redisClient";

export async function cacheGet(key: string): Promise<string | null> {
  try {
    return await redisGet(key);
  } catch {
    return null;
  }
}

export async function cacheSet(
  key: string,
  value: string,
  ttlSeconds?: number
): Promise<boolean> {
  try {
    await redisSet(key, value, ttlSeconds);
    return true;
  } catch {
    return false;
  }
}

export async function cacheInvalidate(key: string): Promise<boolean> {
  try {
    // Redis DEL via cacheSet with 0 TTL (expire immediately)
    await redisSet(key, "", 1);
    return true;
  } catch {
    return false;
  }
}

export async function cacheGetJson<T>(key: string): Promise<T | null> {
  const raw = await cacheGet(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function cacheSetJson(
  key: string,
  value: unknown,
  ttlSeconds?: number
): Promise<boolean> {
  return cacheSet(key, JSON.stringify(value), ttlSeconds);
}
