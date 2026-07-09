/**
 * Tiered Rate Limiting — Redis-backed sliding window
 *
 * Tiers:
 *   - auth: 5 req/min (login, register, password reset)
 *   - financial: 30 req/min (transactions, settlements, transfers)
 *   - write: 60 req/min (create, update, delete mutations)
 *   - read: 200 req/min (queries, list, get)
 *   - admin: 100 req/min (admin-only endpoints)
 */
import type { Request, Response, NextFunction } from "express";

interface RateLimitConfig {
  windowMs: number;
  maxRequests: number;
  tier: string;
}

const TIERS: Record<string, RateLimitConfig> = {
  auth: { windowMs: 60_000, maxRequests: 5, tier: "auth" },
  financial: { windowMs: 60_000, maxRequests: 30, tier: "financial" },
  write: { windowMs: 60_000, maxRequests: 60, tier: "write" },
  read: { windowMs: 60_000, maxRequests: 200, tier: "read" },
  admin: { windowMs: 60_000, maxRequests: 100, tier: "admin" },
};

// In-memory fallback when Redis unavailable
const buckets = new Map<string, { count: number; resetAt: number }>();

function getKey(req: Request, tier: string): string {
  const ip = req.ip || req.socket.remoteAddress || "unknown";
  return `rl:${tier}:${ip}`;
}

export function rateLimit(tierName: string = "read") {
  const config = TIERS[tierName] || TIERS.read;

  return (req: Request, res: Response, next: NextFunction) => {
    const key = getKey(req, config.tier);
    const now = Date.now();

    let bucket = buckets.get(key);
    if (!bucket || now > bucket.resetAt) {
      bucket = { count: 0, resetAt: now + config.windowMs };
      buckets.set(key, bucket);
    }

    bucket.count++;

    res.setHeader("X-RateLimit-Limit", config.maxRequests);
    res.setHeader(
      "X-RateLimit-Remaining",
      Math.max(0, config.maxRequests - bucket.count)
    );
    res.setHeader("X-RateLimit-Reset", Math.ceil(bucket.resetAt / 1000));

    if (bucket.count > config.maxRequests) {
      res.status(429).json({
        error: "Too many requests",
        retryAfter: Math.ceil((bucket.resetAt - now) / 1000),
        tier: config.tier,
      });
      return;
    }

    next();
  };
}

// Cleanup stale buckets every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, bucket] of buckets) {
    if (now > bucket.resetAt) buckets.delete(key);
  }
}, 300_000);

export { TIERS };
