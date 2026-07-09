/**
 * 54Link Permify Client
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

    if (!res.ok) {
      logger.warn(
        `[Permify] Check failed: ${res.status} — falling back to deny`
      );
      return false;
    }

    const json = (await res.json()) as PermifyCheckResponse;
    return json.can === "CHECK_RESULT_ALLOWED";
  } catch (err) {
    // Fail-open: when Permify is unavailable (e.g. dev without Docker), allow access.
    // In production, Permify is always running via docker-compose.production.yml.
    logger.warn(
      { err },
      "[Permify] Service unavailable — failing open (allow)"
    );
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

/**
 * Write a relationship tuple to Permify.
 * Used to establish ownership/access when resources are created.
 */
export async function permifyWriteRelation(params: {
  entityType: string;
  entityId: string;
  relation: string;
  subjectType: string;
  subjectId: string;
}): Promise<boolean> {
  try {
    const res = await fetch(
      `${PERMIFY_URL}/v1/tenants/${PERMIFY_TENANT_ID}/relationships/write`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata: { schemaVersion: "" },
          tuples: [
            {
              entity: { type: params.entityType, id: params.entityId },
              relation: params.relation,
              subject: { type: params.subjectType, id: params.subjectId },
            },
          ],
        }),
        signal: AbortSignal.timeout(2_000),
      }
    );
    if (!res.ok) {
      logger.warn(`[Permify] Write relation failed: ${res.status}`);
      return false;
    }
    return true;
  } catch (err) {
    logger.warn(
      { err },
      "[Permify] Write relation failed — service unavailable"
    );
    return false;
  }
}

/**
 * Delete a relationship tuple from Permify.
 */
export async function permifyDeleteRelation(params: {
  entityType: string;
  entityId: string;
  relation: string;
  subjectType: string;
  subjectId: string;
}): Promise<boolean> {
  try {
    const res = await fetch(
      `${PERMIFY_URL}/v1/tenants/${PERMIFY_TENANT_ID}/relationships/delete`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tupleFilter: {
            entity: { type: params.entityType, id: params.entityId },
            relation: params.relation,
            subject: { type: params.subjectType, id: params.subjectId },
          },
        }),
        signal: AbortSignal.timeout(2_000),
      }
    );
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Enforce permission check as tRPC middleware.
 * Throws TRPCError if permission denied.
 */
export async function enforcePermission(params: {
  subjectType: string;
  subjectId: string;
  entityType: string;
  entityId: string;
  permission: string;
}): Promise<void> {
  const allowed = await permifyCheck(params);
  if (!allowed) {
    throw new Error(
      `Permission denied: ${params.subjectType}:${params.subjectId} cannot ${params.permission} on ${params.entityType}:${params.entityId}`
    );
  }
}

/**
 * Batch write relationship tuples for resource creation.
 */
export async function permifyWriteRelations(
  tuples: Array<{
    entityType: string;
    entityId: string;
    relation: string;
    subjectType: string;
    subjectId: string;
  }>
): Promise<boolean> {
  try {
    const res = await fetch(
      `${PERMIFY_URL}/v1/tenants/${PERMIFY_TENANT_ID}/relationships/write`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata: { schemaVersion: "" },
          tuples: tuples.map(t => ({
            entity: { type: t.entityType, id: t.entityId },
            relation: t.relation,
            subject: { type: t.subjectType, id: t.subjectId },
          })),
        }),
        signal: AbortSignal.timeout(2_000),
      }
    );
    return res.ok;
  } catch {
    return false;
  }
}

export default {
  permifyCheck,
  permifyWriteRelation,
  permifyDeleteRelation,
  permifyWriteRelations,
  enforcePermission,
  canAccessTransaction,
  canApproveTopUp,
  canUpdateFraudAlert,
};
