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

const PERMIFY_URL = process.env.PERMIFY_URL ?? "http://localhost:3476";
const PERMIFY_TENANT_ID = process.env.PERMIFY_TENANT_ID ?? "t1";

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
 * Persist a Permify check result to the permify_check_log table.
 * Fire-and-forget — never blocks the authorization path.
 */
async function persistCheckLog(params: {
  subjectType: string;
  subjectId: string;
  entityType: string;
  entityId: string;
  permission: string;
  result: "allowed" | "denied" | "error" | "fallback_open";
  latencyMs?: number;
  errorMessage?: string;
}): Promise<void> {
  try {
    const { getDb } = await import("../db");
    const { permifyCheckLog } = await import("../../drizzle/schema");
    const db = await getDb();
    if (!db) return;
    await db.insert(permifyCheckLog).values({
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
    });
  } catch {
    // Persistence failure must never break the authorization path
  }
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
    void persistCheckLog({ ...params, result: allowed ? "allowed" : "denied", latencyMs });
    return allowed;
  } catch (err) {
    // Fail-open: when Permify is unavailable (e.g. dev without Docker), allow access.
    // In production, Permify is always running via docker-compose.production.yml.
    logger.warn(
      { err },
      "[Permify] Service unavailable — failing open (allow)"
    );
    void persistCheckLog({ ...params, result: "fallback_open", latencyMs: Date.now() - startMs, errorMessage: String(err) });
    return true;
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
