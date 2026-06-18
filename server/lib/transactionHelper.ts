/**
 * Transaction Helper — wraps DB operations in transactions with retry logic.
 * Provides idempotency key checking and audit trail integration.
 */
import { getDb } from "../db";
import { sql, eq } from "drizzle-orm";
import { logAudit } from "./auditTrail";

/**
 * Execute a DB operation within a transaction.
 * Automatically retries on serialization failures (up to 3 times).
 */
export async function withTransaction<T>(
  fn: (tx: any) => Promise<T>,
  label?: string
): Promise<T> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");

  let attempts = 0;
  const maxRetries = 3;

  while (attempts < maxRetries) {
    try {
      return await (db as any).transaction(async (tx: any) => {
        return await fn(tx);
      });
    } catch (err: any) {
      attempts++;
      if (err?.code === "40001" && attempts < maxRetries) {
        // Serialization failure — retry
        continue;
      }
      throw err;
    }
  }

  throw new Error(
    `Transaction failed after ${maxRetries} retries: ${label ?? "unknown"}`
  );
}

/**
 * Idempotency key store — prevents duplicate financial operations.
 * Uses the idempotency_keys table if it exists, otherwise in-memory fallback.
 */
const idempotencyCache = new Map<string, { result: any; expiresAt: number }>();
const IDEMPOTENCY_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

export async function withIdempotency<T>(
  key: string,
  fn: () => Promise<T>
): Promise<T> {
  // Check in-memory cache first
  const cached = idempotencyCache.get(key);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.result as T;
  }

  // Check DB
  try {
    const db = await getDb();
    if (db) {
      const [existing] = await db.execute(
        sql`SELECT response_data FROM idempotency_keys WHERE idempotency_key = ${key} AND expires_at > NOW() LIMIT 1`
      );
      if (existing && (existing as any).response_data) {
        const result = JSON.parse((existing as any).response_data);
        idempotencyCache.set(key, {
          result,
          expiresAt: Date.now() + IDEMPOTENCY_TTL_MS,
        });
        return result as T;
      }
    }
  } catch {
    // DB check failed — proceed without DB idempotency
  }

  // Execute the operation
  const result = await fn();

  // Store the result
  idempotencyCache.set(key, {
    result,
    expiresAt: Date.now() + IDEMPOTENCY_TTL_MS,
  });

  // Persist to DB
  try {
    const db = await getDb();
    if (db) {
      await db.execute(
        sql`INSERT INTO idempotency_keys (idempotency_key, response_data, expires_at) VALUES (${key}, ${JSON.stringify(result)}, NOW() + INTERVAL '24 hours') ON CONFLICT (idempotency_key) DO NOTHING`
      );
    }
  } catch {
    // DB store failed — in-memory cache still protects
  }

  // Evict old entries periodically
  if (idempotencyCache.size > 10000) {
    const now = Date.now();
    for (const [k, v] of idempotencyCache) {
      if (v.expiresAt < now) idempotencyCache.delete(k);
    }
  }

  return result;
}

/**
 * Validate a financial amount — positive, within limits, proper precision.
 */
export function validateAmount(
  amount: number,
  options?: { min?: number; max?: number; currency?: string }
): { valid: boolean; error?: string } {
  const min = options?.min ?? 0;
  const max = options?.max ?? 100_000_000; // 100M default cap

  if (!Number.isFinite(amount))
    return { valid: false, error: "Amount must be a finite number" };
  if (amount <= min)
    return {
      valid: false,
      error: `Amount must be greater than ${min}`,
    };
  if (amount > max)
    return {
      valid: false,
      error: `Amount exceeds maximum of ${max.toLocaleString()}`,
    };

  // Check for excessive decimal places (max 2 for most currencies)
  const decimalStr = amount.toString().split(".")[1];
  if (decimalStr && decimalStr.length > 2) {
    return {
      valid: false,
      error: "Amount cannot have more than 2 decimal places",
    };
  }

  return { valid: true };
}

/**
 * Validate a status transition against allowed transitions.
 */
export function validateStatusTransition(
  current: string,
  next: string,
  allowedTransitions: Record<string, string[]>
): { valid: boolean; error?: string } {
  const allowed = allowedTransitions[current];
  if (!allowed) {
    return {
      valid: false,
      error: `Unknown status: ${current}`,
    };
  }
  if (!allowed.includes(next)) {
    return {
      valid: false,
      error: `Cannot transition from '${current}' to '${next}'. Allowed: ${allowed.join(", ")}`,
    };
  }
  return { valid: true };
}

/**
 * Log a financial audit event.
 */
export function auditFinancialAction(
  action: "CREATE" | "UPDATE" | "DELETE" | "APPROVE" | "REJECT",
  resource: string,
  resourceId: string,
  description: string,
  metadata?: Record<string, unknown>
) {
  logAudit({
    userId: null,
    userRole: "system",
    action,
    resource,
    resourceId,
    description,
    ipAddress: "internal",
    userAgent: "server",
    severity: "high",
    category: "financial",
    metadata,
  });
}
