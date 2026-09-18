import { createHash } from "crypto";

/**
 * Deterministic Temporal workflowId.
 *
 * workflowId = hash(tenantId, entityType, entityId) so that a retried request
 * for the SAME entity targets the SAME workflow execution. Temporal rejects
 * duplicate starts for an already-running workflowId (the runner resumes the
 * existing execution instead), which prevents duplicate onboarding workflows
 * caused by client retries / double-submits.
 */
export function deterministicWorkflowId(
  prefix: string,
  tenantId: string,
  entityType: string,
  entityId: string,
): string {
  const hash = createHash("sha256")
    .update(`${tenantId}:${entityType}:${entityId}`)
    .digest("hex")
    .slice(0, 32);
  return `${prefix}_${entityType}_${hash}`;
}
