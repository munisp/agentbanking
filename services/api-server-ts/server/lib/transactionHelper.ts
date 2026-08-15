/**
 * Transaction Helper — wraps DB operations in transactions with retry logic.
 * Provides idempotency key checking and audit trail integration.
 */
import { getDb } from "../db";
import { sql, eq } from "drizzle-orm";
import { logAudit } from "./auditTrail";
import crypto from "crypto";
import { TRPCError } from "@trpc/server";

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
 *
 * FF-7 hardening (claim-first, payload-bound, fail-closed):
 *  - The key is CLAIMED with INSERT ... ON CONFLICT DO NOTHING *before* the
 *    protected operation runs — the previous check-then-act order had a TOCTOU
 *    window where two concurrent requests both passed the existence check.
 *  - Each claim binds the key to a SHA-256 hash of the request payload
 *    (`requestHash`). Reusing a key with a different payload → 409 CONFLICT.
 *  - Any DB error while claiming THROWS (fail closed). The old code caught the
 *    error and "proceeded without idempotency", executing money movement
 *    completely unprotected during exactly the failure window (DB trouble)
 *    where duplicate submissions are most likely.
 *  - The claim row carries a status envelope: pending → completed | failed.
 *    A failed claim may be atomically re-claimed by a retry presenting the
 *    same payload; a pending claim means another execution is in flight → 409.
 *
 * The idempotency_keys table has no dedicated hash/status columns, so the
 * envelope is stored inside `response_data` as JSON:
 *   { v: 1, requestHash, status, result?, error? }
 * Rows written before this change hold a bare result JSON; they decode as
 * legacy completed claims with an empty requestHash (see decodeEnvelope).
 */
export interface IdempotencyEnvelope {
  v: 1;
  requestHash: string;
  status: "pending" | "completed" | "failed";
  result?: unknown;
  error?: string;
}

/** Deterministic JSON serialization (sorted object keys) for payload hashing. */
function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value) ?? "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  const obj = value as Record<string, unknown>;
  return `{${Object.keys(obj)
    .sort()
    .map(k => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
    .join(",")}}`;
}

/** SHA-256 over the canonical JSON of the request payload. */
export function hashIdempotencyPayload(payload: unknown): string {
  return crypto
    .createHash("sha256")
    .update(stableStringify(payload ?? null))
    .digest("hex");
}

function encodeEnvelope(env: IdempotencyEnvelope): string {
  return JSON.stringify(env);
}

function decodeEnvelope(raw: unknown): IdempotencyEnvelope | null {
  if (typeof raw !== "string" || raw.length === 0) return null;
  try {
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      parsed.v === 1 &&
      typeof parsed.requestHash === "string"
    ) {
      return parsed as IdempotencyEnvelope;
    }
    // Legacy row (pre-FF-7): bare result JSON. Treated as a completed claim
    // whose payload hash is unknown — replay is allowed without payload
    // binding for these rows only (24h TTL bounds the exposure).
    return { v: 1, requestHash: "", status: "completed", result: parsed };
  } catch {
    return null;
  }
}

/** drizzle node-postgres execute() returns a pg QueryResult; tolerate both shapes. */
function rowsOf(execResult: unknown): any[] {
  const r = execResult as any;
  return (r && Array.isArray(r.rows) ? r.rows : r) ?? [];
}

export type IdempotencyClaimOutcome =
  | { kind: "claimed" }
  | { kind: "replay"; result: unknown };

/**
 * Claim an idempotency key BEFORE the protected operation. Fail-closed:
 * any DB error propagates as an exception — the caller must NOT proceed.
 *
 * Outcomes:
 *  - "claimed"  → caller must run the operation, then complete/fail the claim
 *  - "replay"   → same key + same payload already completed; return `result`
 *  - throws TRPCError CONFLICT → key reused with a different payload, or a
 *    duplicate execution is currently in flight
 */
export async function claimIdempotencyKey(
  key: string,
  requestHash: string
): Promise<IdempotencyClaimOutcome> {
  const db = await getDb();
  if (!db || (db as any)._isNoop) {
    throw new Error(
      "Database not available — refusing to execute a financial operation without idempotency protection"
    );
  }
  const pending = encodeEnvelope({ v: 1, requestHash, status: "pending" });
  const claimedRows = rowsOf(
    await db.execute(
      sql`INSERT INTO idempotency_keys (idempotency_key, response_data, expires_at)
          VALUES (${key}, ${pending}, NOW() + INTERVAL '24 hours')
          ON CONFLICT (idempotency_key) DO NOTHING
          RETURNING idempotency_key`
    )
  );
  if (claimedRows.length > 0) return { kind: "claimed" };

  // Key already exists — inspect the prior claim.
  const existingRows = rowsOf(
    await db.execute(
      sql`SELECT response_data, expires_at FROM idempotency_keys WHERE idempotency_key = ${key} LIMIT 1`
    )
  );
  const rawData = existingRows[0]?.response_data as string | undefined;
  const expiresAt = existingRows[0]?.expires_at;
  const isExpired =
    expiresAt != null && new Date(expiresAt).getTime() <= Date.now();
  if (isExpired) {
    // Expired claim — atomically re-claim via compare-and-swap on the exact
    // row content so precisely one waiter resumes with a fresh 24h window.
    const reclaimed = rowsOf(
      await db.execute(
        sql`UPDATE idempotency_keys
            SET response_data = ${pending}, expires_at = NOW() + INTERVAL '24 hours'
            WHERE idempotency_key = ${key} AND response_data = ${rawData}
            RETURNING idempotency_key`
      )
    );
    if (reclaimed.length > 0) return { kind: "claimed" };
    // Lost the re-claim race — another request now holds this key.
    throw new TRPCError({
      code: "CONFLICT",
      message: "Duplicate request is already in progress",
    });
  }
  const env = decodeEnvelope(rawData);
  if (!env) {
    // Unreadable claim row — fail closed rather than guess.
    throw new TRPCError({
      code: "CONFLICT",
      message: "Idempotency key exists with an unreadable claim record",
    });
  }
  if (env.requestHash !== "" && env.requestHash !== requestHash) {
    throw new TRPCError({
      code: "CONFLICT",
      message:
        "Idempotency key was already used with a different request payload",
    });
  }
  if (env.status === "completed") {
    return { kind: "replay", result: env.result };
  }
  if (env.status === "failed") {
    // Prior attempt failed — atomically re-claim via compare-and-swap on the
    // exact row content so that precisely one concurrent retry resumes.
    const reclaimed = rowsOf(
      await db.execute(
        sql`UPDATE idempotency_keys
            SET response_data = ${pending}, expires_at = NOW() + INTERVAL '24 hours'
            WHERE idempotency_key = ${key} AND response_data = ${rawData}
            RETURNING idempotency_key`
      )
    );
    if (reclaimed.length > 0) return { kind: "claimed" };
    throw new TRPCError({
      code: "CONFLICT",
      message: "Duplicate request is already being retried",
    });
  }
  // status === "pending": another execution holds the claim right now.
  throw new TRPCError({
    code: "CONFLICT",
    message: "Duplicate request is already in progress",
  });
}

/**
 * Mark a claimed key completed and store the operation result for replays.
 * Best-effort finalization: the protected operation already succeeded, so on
 * DB error we fall back to marking the claim failed (retry-resumable) instead
 * of leaving a permanently stuck "pending" claim. Never throws.
 */
export async function completeIdempotencyKey(
  key: string,
  requestHash: string,
  result: unknown
): Promise<void> {
  try {
    const db = await getDb();
    if (!db || (db as any)._isNoop) return;
    const env = encodeEnvelope({
      v: 1,
      requestHash,
      status: "completed",
      result: result ?? null,
    });
    await db.execute(
      sql`UPDATE idempotency_keys SET response_data = ${env} WHERE idempotency_key = ${key}`
    );
  } catch (err) {
    console.error(
      "[Idempotency] Failed to finalize claim as completed; marking failed instead:",
      err
    );
    await failIdempotencyKey(key, requestHash, "completion record failed");
  }
}

/**
 * Mark a claimed key failed so a retry with the same key + payload can
 * safely resume. Best-effort, never throws.
 */
export async function failIdempotencyKey(
  key: string,
  requestHash: string,
  errorMessage: string
): Promise<void> {
  try {
    const db = await getDb();
    if (!db || (db as any)._isNoop) return;
    const env = encodeEnvelope({
      v: 1,
      requestHash,
      status: "failed",
      error: errorMessage.slice(0, 500),
    });
    await db.execute(
      sql`UPDATE idempotency_keys SET response_data = ${env} WHERE idempotency_key = ${key}`
    );
  } catch (err) {
    console.error("[Idempotency] Failed to mark claim as failed:", err);
  }
}

/**
 * Execute an operation with idempotency protection (claim-first, fail-closed).
 *
 * Backward-compatible signature: `withIdempotency(key, fn)`. Pass
 * `opts.payload` to bind the key to the request payload; without it the key
 * is bound to a hash of `null` (payload binding only enforced across callers
 * that both supply a payload).
 */
export async function withIdempotency<T>(
  key: string,
  fn: () => Promise<T>,
  opts?: { payload?: unknown }
): Promise<T> {
  const requestHash = hashIdempotencyPayload(opts?.payload ?? null);
  // Claim-first: throws (fail closed) on any DB error — never proceeds
  // without idempotency protection.
  const claim = await claimIdempotencyKey(key, requestHash);
  if (claim.kind === "replay") {
    return claim.result as T;
  }
  try {
    const result = await fn();
    await completeIdempotencyKey(key, requestHash, result ?? null);
    return result;
  } catch (err) {
    await failIdempotencyKey(
      key,
      requestHash,
      err instanceof Error ? err.message : String(err)
    );
    throw err;
  }
}

/**
 * Idempotency for DB-only operations: the key claim and `fn` execute in the
 * SAME database transaction (via withTransaction above, incl. serialization
 * retries). If `fn` throws, the whole transaction — including the claim —
 * rolls back, so a retry with the same key + payload can safely re-claim.
 * A Temporal (or other) retry of a completed operation replays the stored
 * result and no-ops.
 */
export async function withIdempotencyTx<T>(
  key: string,
  payload: unknown,
  fn: (tx: any) => Promise<T>,
  label?: string
): Promise<T> {
  const requestHash = hashIdempotencyPayload(payload ?? null);
  return withTransaction(async (tx: any) => {
    const pending = encodeEnvelope({ v: 1, requestHash, status: "pending" });
    const claimedRows = rowsOf(
      await tx.execute(
        sql`INSERT INTO idempotency_keys (idempotency_key, response_data, expires_at)
            VALUES (${key}, ${pending}, NOW() + INTERVAL '24 hours')
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING idempotency_key`
      )
    );
    if (claimedRows.length === 0) {
      const existingRows = rowsOf(
        await tx.execute(
          sql`SELECT response_data FROM idempotency_keys WHERE idempotency_key = ${key} LIMIT 1`
        )
      );
      const rawData = existingRows[0]?.response_data as string | undefined;
      const env = decodeEnvelope(rawData);
      if (!env) {
        throw new TRPCError({
          code: "CONFLICT",
          message: "Idempotency key exists with an unreadable claim record",
        });
      }
      if (env.requestHash !== "" && env.requestHash !== requestHash) {
        throw new TRPCError({
          code: "CONFLICT",
          message:
            "Idempotency key was already used with a different request payload",
        });
      }
      if (env.status === "completed") {
        return env.result as T; // retry no-op: replay stored result
      }
      if (env.status === "failed") {
        // Re-claim atomically inside this transaction, then proceed.
        const reclaimed = rowsOf(
          await tx.execute(
            sql`UPDATE idempotency_keys
                SET response_data = ${pending}, expires_at = NOW() + INTERVAL '24 hours'
                WHERE idempotency_key = ${key} AND response_data = ${rawData}
                RETURNING idempotency_key`
          )
        );
        if (reclaimed.length === 0) {
          throw new TRPCError({
            code: "CONFLICT",
            message: "Duplicate request is already being retried",
          });
        }
      } else {
        throw new TRPCError({
          code: "CONFLICT",
          message: "Duplicate request is already in progress",
        });
      }
    }
    const result = await fn(tx);
    const completed = encodeEnvelope({
      v: 1,
      requestHash,
      status: "completed",
      result: result ?? null,
    });
    await tx.execute(
      sql`UPDATE idempotency_keys SET response_data = ${completed} WHERE idempotency_key = ${key}`
    );
    return result;
  }, label ?? `withIdempotencyTx:${key}`);
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
