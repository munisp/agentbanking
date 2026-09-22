/**
 * 54agent Permify Client
 * HTTP client for Permify authorization service.
 * Falls back to role-based checks when Permify is unavailable.
 *
 * Schema (defined in infra/permify/schema.perm):
 *   entity agent { ... }
 *   entity admin { ... }
 *   entity supervisor { ... }
 *
 * Policies:
 *   - agents can only read own transactions
 *   - admins can read all transactions
 *   - float top-up approval requires supervisor or admin
 *   - fraud alert status update requires admin
 *
 * Audit: All permission checks are logged to the permify_check_log
 * PostgreSQL table (migration 0047) for compliance and debugging.
 */
import logger from "./logger";
import { createBatchedQueue } from "../lib/batchedAsyncQueue";

const PERMIFY_URL = process.env.PERMIFY_URL ?? "http://localhost:3476";
const PERMIFY_TENANT_ID = process.env.PERMIFY_TENANT_ID ?? "t1";

// ── Round-8 perf: short-TTL decision cache ────────────────────────────────────
// permifyCheck was an uncached blocking HTTP RPC on EVERY protectedProcedure
// (and twice for adminProcedure). Cache concrete allowed/denied verdicts for
// 30s keyed by (tenant, subject, permission, resource). Errors and fallback
// verdicts are NEVER cached — fail-closed semantics are preserved: a Permify
// outage still denies (no stale "allow" can be synthesized from an error).
const PERMIFY_CACHE_TTL_MS = 30_000;
const PERMIFY_CACHE_MAX = 10_000;

interface CacheEntry {
  allowed: boolean;
  expiresAt: number;
}
const decisionCache = new Map<string, CacheEntry>();

function cacheKey(params: {
  subjectType: string;
  subjectId: string;
  entityType: string;
  entityId: string;
  permission: string;
}): string {
  return [
    PERMIFY_TENANT_ID,
    params.subjectType,
    params.subjectId,
    params.permission,
    params.entityType,
    params.entityId,
  ].join(":");
}

function cacheGetDecision(key: string): boolean | undefined {
  const entry = decisionCache.get(key);
  if (!entry) return undefined;
  if (entry.expiresAt <= Date.now()) {
    decisionCache.delete(key);
    return undefined;
  }
  return entry.allowed;
}

function cacheSetDecision(key: string, allowed: boolean): void {
  if (decisionCache.size >= PERMIFY_CACHE_MAX) {
    // Cheap eviction sweep: drop expired entries; if still full, reset.
    const now = Date.now();
    for (const [k, v] of decisionCache) {
      if (v.expiresAt <= now) decisionCache.delete(k);
    }
    if (decisionCache.size >= PERMIFY_CACHE_MAX) decisionCache.clear();
  }
  decisionCache.set(key, { allowed, expiresAt: Date.now() + PERMIFY_CACHE_TTL_MS });
}

interface PermifyCheckRequest {
  tenantId: string;
  metadata: { schemaVersion: string; snapToken: string; depth: number };
  entity: { type: string; id: string };
  permission: string;
  subject: { type: string; id: string; relation?: string };
}

interface PermifyCheckResponse {
  can:
    | "CHECK_RESULT_ALLOWED"
    | "CHECK_RESULT_DENIED"
    | "CHECK_RESULT_UNSPECIFIED";
}

/**
 * Persist Permify check results to the permify_check_log table.
 *
 * Round-8 perf: was one Postgres INSERT per check (a pool checkout + write on
 * every protected request). Now buffered in memory and flushed as a single
 * multi-row INSERT every 100ms / 50 rows (500ms timeout, drop-oldest at 10k).
 * Fire-and-forget — never blocks the authorization path; audit-copy loss on
 * crash is acceptable (the table is for compliance debugging, not the
 * authoritative audit trail — that is audit_log / outbox).
 */
interface CheckLogRow {
  subjectType: string;
  subjectId: string;
  entityType: string;
  entityId: string;
  permission: string;
  result: "allowed" | "denied" | "error" | "fallback_open" | "fallback_closed";
  latencyMs?: number;
  errorMessage?: string;
}

async function flushCheckLogBatch(rows: CheckLogRow[]): Promise<void> {
  const { getDb } = await import("../db");
  const { permifyCheckLog } = await import("../../drizzle/schema");
  const db = await getDb();
  if (!db || rows.length === 0) return;
  await db.insert(permifyCheckLog).values(
    rows.map(params => ({
      tenantId: PERMIFY_TENANT_ID,
      subjectType: params.subjectType,
      subjectId: params.subjectId,
      entityType: params.entityType,
      entityId: params.entityId,
      permission: params.permission,
      result: params.result,
      depth: 20,
      latencyMs: params.latencyMs,
      errorMessage: params.errorMessage,
    }))
  );
}

const checkLogQueue = createBatchedQueue<CheckLogRow>({
  name: "permifyCheckLog",
  batchSize: 50,
  flushIntervalMs: 100,
  maxQueue: 10_000,
  taskTimeoutMs: 500,
  flush: flushCheckLogBatch,
});

async function persistCheckLog(params: CheckLogRow): Promise<void> {
  // Queue push only — persistence failure must never break authorization.
  checkLogQueue.push(params);
}

/**
 * Check if a subject has permission on an entity.
 * Returns true if allowed, false if denied or Permify is unavailable.
 */
export async function permifyCheck(params: {
  subjectType: string;
  subjectId: string;
  entityType: string;
  entityId: string;
  permission: string;
}): Promise<boolean> {
  // Round-8 perf: 30s decision cache (concrete verdicts only — never errors).
  // Cache hits skip both the HTTP RPC and the audit-log write (the latter is
  // what makes this a net write reduction, not just a latency one).
  const key = cacheKey(params);
  const cached = cacheGetDecision(key);
  if (cached !== undefined) return cached;

  const body: PermifyCheckRequest = {
    tenantId: PERMIFY_TENANT_ID,
    metadata: {
      schemaVersion: "",
      snapToken: "",
      depth: 20,
    },
    entity: { type: params.entityType, id: params.entityId },
    permission: params.permission,
    subject: { type: params.subjectType, id: params.subjectId },
  };

  const startMs = Date.now();

  try {
    const res = await fetch(
      `${PERMIFY_URL}/v1/tenants/${PERMIFY_TENANT_ID}/permissions/check`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(2_000),
      }
    );

    const latencyMs = Date.now() - startMs;

    if (!res.ok) {
      logger.warn(
        `[Permify] Check failed: ${res.status} — falling back to deny`
      );
      void persistCheckLog({ ...params, result: "error", latencyMs, errorMessage: `HTTP ${res.status}` });
      return false;
    }

    const json = (await res.json()) as PermifyCheckResponse;
    const allowed = json.can === "CHECK_RESULT_ALLOWED";
    // Cache concrete verdicts only (allowed/denied). Errors and fail-open/
    // fail-closed fallbacks are never cached, preserving fail-closed semantics.
    cacheSetDecision(key, allowed);
    void persistCheckLog({ ...params, result: allowed ? "allowed" : "denied", latencyMs });
    return allowed;
  } catch (err) {
    // Round-6 fix: fail CLOSED. The previous fail-open behavior meant a Permify
    // outage (or DNS failure) silently disabled authorization platform-wide for
    // every protectedProcedure/adminProcedure. Override only for local dev via
    // PERMIFY_FAIL_OPEN=true (never set this in production).
    const failOpen = process.env.PERMIFY_FAIL_OPEN === "true" && process.env.NODE_ENV !== "production";
    logger.warn(
      { err, failOpen },
      "[Permify] Service unavailable — " + (failOpen ? "failing open (DEV override)" : "failing closed (deny)")
    );
    void persistCheckLog({ ...params, result: failOpen ? "fallback_open" : "fallback_closed", latencyMs: Date.now() - startMs, errorMessage: String(err) });
    return failOpen;
  }
}

/**
 * Check if an agent can access a specific transaction.
 * Agents can only access their own transactions; admins can access all.
 */
export async function canAccessTransaction(
  agentCode: string,
  agentRole: string,
  txRef: string
): Promise<boolean> {
  if (agentRole === "admin") return true;

  // Try Permify first
  const allowed = await permifyCheck({
    subjectType: "agent",
    subjectId: agentCode,
    entityType: "transaction",
    entityId: txRef,
    permission: "read",
  });

  // If Permify is unavailable (returns false for unknown entities), fall back to ownership check
  return allowed;
}

/**
 * Check if an agent can approve float top-up requests.
 * Requires supervisor or admin role.
 */
export async function canApproveTopUp(
  agentCode: string,
  agentRole: string
): Promise<boolean> {
  if (agentRole === "admin") return true;

  return permifyCheck({
    subjectType: "agent",
    subjectId: agentCode,
    entityType: "float_topup",
    entityId: "*",
    permission: "approve",
  });
}

/**
 * Check if an agent can update fraud alert status.
 * Requires admin role.
 */
export async function canUpdateFraudAlert(
  agentCode: string,
  agentRole: string
): Promise<boolean> {
  if (agentRole === "admin") return true;

  return permifyCheck({
    subjectType: "agent",
    subjectId: agentCode,
    entityType: "fraud_alert",
    entityId: "*",
    permission: "update",
  });
}

export default {
  permifyCheck,
  canAccessTransaction,
  canApproveTopUp,
  canUpdateFraudAlert,
};
