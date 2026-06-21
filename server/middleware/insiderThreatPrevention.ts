/**
 * Insider Threat Prevention Middleware
 *
 * Controls:
 * 1. Separation of duties (self-approval blocking)
 * 2. Maker-checker dual-control for high-value operations
 * 3. Threshold-based escalation (tiered approval)
 * 4. Step-up authentication for privileged actions
 * 5. Privileged session timeout (15 min idle)
 * 6. Velocity/pattern detection for staff actions
 */
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import { sql, eq, and, gte } from "drizzle-orm";
import { publishEvent } from "../kafkaClient";
import { dapr } from "./middlewareConnectors";
import crypto from "crypto";

// ── Types ────────────────────────────────────────────────────────────────────

export interface ApprovalRequest {
  id: string;
  type: string;
  requestedBy: number;
  requestedByCode: string;
  amount: number;
  currency: string;
  resource: string;
  resourceId: string;
  metadata: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "expired";
  requiredApprovals: number;
  approvals: Array<{ agentId: number; agentCode: string; timestamp: string }>;
  rejections: Array<{ agentId: number; agentCode: string; reason: string; timestamp: string }>;
  expiresAt: string;
  createdAt: string;
}

// ── Threshold Configuration ──────────────────────────────────────────────────

export const APPROVAL_THRESHOLDS = {
  // Tier 1: No additional approval needed
  tier1: { min: 0, max: 500_000, approvals: 0, label: "Standard" },
  // Tier 2: One additional approver (maker-checker)
  tier2: { min: 500_001, max: 5_000_000, approvals: 1, label: "Dual Control" },
  // Tier 3: Two approvers + compliance + 30-min cooling period
  tier3: { min: 5_000_001, max: Infinity, approvals: 2, label: "Compliance Review" },
} as const;

// Operations that ALWAYS require maker-checker regardless of amount
export const ALWAYS_DUAL_CONTROL = [
  "loan_disbursement",
  "commission_payout_bulk",
  "fx_conversion_large",
  "float_adjustment",
  "fee_override",
  "account_privilege_change",
  "agent_deactivation",
  "reversal_approval",
  "chargeback_resolution",
  "system_config_change",
] as const;

// Cooling period (ms) for Tier 3 transactions
const TIER3_COOLING_PERIOD = 30 * 60 * 1000; // 30 minutes

// ── 1. Separation of Duties ─────────────────────────────────────────────────

export function enforceSeparationOfDuties(
  approverAgentId: number,
  requestedByAgentId: number,
  operation: string
): void {
  if (approverAgentId === requestedByAgentId) {
    throw new TRPCError({
      code: "FORBIDDEN",
      message: `Separation of duties violation: cannot approve own ${operation} request`,
    });
  }
}

// ── 2. Maker-Checker Dual Control ───────────────────────────────────────────

export function getRequiredApprovals(
  amount: number,
  operationType: string
): { approvals: number; tier: string; coolingPeriod: number } {
  // Operations that always need dual control
  if (ALWAYS_DUAL_CONTROL.includes(operationType as any)) {
    if (amount > APPROVAL_THRESHOLDS.tier3.min) {
      return { approvals: 2, tier: "tier3", coolingPeriod: TIER3_COOLING_PERIOD };
    }
    return { approvals: 1, tier: "tier2", coolingPeriod: 0 };
  }

  // Threshold-based
  if (amount > APPROVAL_THRESHOLDS.tier3.min) {
    return { approvals: 2, tier: "tier3", coolingPeriod: TIER3_COOLING_PERIOD };
  }
  if (amount > APPROVAL_THRESHOLDS.tier2.min) {
    return { approvals: 1, tier: "tier2", coolingPeriod: 0 };
  }
  return { approvals: 0, tier: "tier1", coolingPeriod: 0 };
}

export async function createApprovalRequest(params: {
  type: string;
  requestedBy: number;
  requestedByCode: string;
  amount: number;
  currency?: string;
  resource: string;
  resourceId: string;
  metadata?: Record<string, unknown>;
}): Promise<ApprovalRequest> {
  const { approvals, tier, coolingPeriod } = getRequiredApprovals(
    params.amount,
    params.type
  );

  const request: ApprovalRequest = {
    id: `APR-${crypto.randomUUID().slice(0, 12).toUpperCase()}`,
    type: params.type,
    requestedBy: params.requestedBy,
    requestedByCode: params.requestedByCode,
    amount: params.amount,
    currency: params.currency ?? "NGN",
    resource: params.resource,
    resourceId: params.resourceId,
    metadata: params.metadata ?? {},
    status: "pending",
    requiredApprovals: approvals,
    approvals: [],
    rejections: [],
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // 24h
    createdAt: new Date().toISOString(),
  };

  // Store in DB
  const db = await getDb();
  if (db) {
    await db.execute(
      sql`INSERT INTO platform_settings (key, value) VALUES (
        ${`approval_request_${request.id}`},
        ${JSON.stringify(request)}
      ) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`
    );
  }

  // Kafka event for approval workflow
  publishEvent("insider.approval.requested", request.id, {
    eventType: "approval_requested",
    requestId: request.id,
    requestType: request.type,
    amount: request.amount,
    requestedBy: request.requestedByCode,
    tier,
    coolingPeriod,
  }).catch(() => {});

  // Dapr pub/sub for real-time notification
  dapr.publishEvent("pubsub", "insider.approval.pending", {
    requestId: request.id,
    type: params.type,
    amount: params.amount,
    requestedBy: params.requestedByCode,
    tier,
    expiresAt: request.expiresAt,
  }).catch(() => {});

  await writeAuditLog({
    agentId: params.requestedBy,
    agentCode: params.requestedByCode,
    action: "APPROVAL_REQUESTED",
    resource: params.resource,
    resourceId: params.resourceId,
    status: "success",
    metadata: { approvalId: request.id, tier, requiredApprovals: approvals },
  });

  return request;
}

export async function processApproval(params: {
  requestId: string;
  approverAgentId: number;
  approverAgentCode: string;
  approverRole: string;
  action: "approve" | "reject";
  reason?: string;
}): Promise<{ status: string; canExecute: boolean }> {
  const db = await getDb();
  if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

  // Fetch the approval request
  const rows = await db.execute(
    sql`SELECT value FROM platform_settings WHERE key = ${`approval_request_${params.requestId}`}`
  );
  const row = (rows as any).rows?.[0] ?? (rows as any)[0];
  if (!row) throw new TRPCError({ code: "NOT_FOUND", message: "Approval request not found" });

  const request: ApprovalRequest = JSON.parse(String(row.value));

  // Check expiration
  if (new Date(request.expiresAt) < new Date()) {
    request.status = "expired";
    await db.execute(
      sql`UPDATE platform_settings SET value = ${JSON.stringify(request)} WHERE key = ${`approval_request_${params.requestId}`}`
    );
    throw new TRPCError({ code: "BAD_REQUEST", message: "Approval request has expired" });
  }

  // Separation of duties: approver cannot be the requester
  enforceSeparationOfDuties(params.approverAgentId, request.requestedBy, request.type);

  // Check if this approver already acted
  const alreadyApproved = request.approvals.some(a => a.agentId === params.approverAgentId);
  if (alreadyApproved) {
    throw new TRPCError({ code: "BAD_REQUEST", message: "You have already approved this request" });
  }

  if (params.action === "reject") {
    request.rejections.push({
      agentId: params.approverAgentId,
      agentCode: params.approverAgentCode,
      reason: params.reason ?? "Rejected",
      timestamp: new Date().toISOString(),
    });
    request.status = "rejected";
  } else {
    request.approvals.push({
      agentId: params.approverAgentId,
      agentCode: params.approverAgentCode,
      timestamp: new Date().toISOString(),
    });

    if (request.approvals.length >= request.requiredApprovals) {
      request.status = "approved";
    }
  }

  // Persist
  await db.execute(
    sql`UPDATE platform_settings SET value = ${JSON.stringify(request)} WHERE key = ${`approval_request_${params.requestId}`}`
  );

  // Audit + events
  await writeAuditLog({
    agentId: params.approverAgentId,
    agentCode: params.approverAgentCode,
    action: params.action === "approve" ? "APPROVAL_GRANTED" : "APPROVAL_REJECTED",
    resource: request.resource,
    resourceId: request.resourceId,
    status: "success",
    metadata: {
      approvalId: request.id,
      originalRequester: request.requestedByCode,
      amount: request.amount,
      reason: params.reason,
    },
  });

  publishEvent("insider.approval.actioned", request.id, {
    type: `approval_${params.action}ed`,
    requestId: request.id,
    approverCode: params.approverAgentCode,
    status: request.status,
  }).catch(() => {});

  dapr.publishEvent("pubsub", `insider.approval.${params.action}ed`, {
    requestId: request.id,
    status: request.status,
    approverCode: params.approverAgentCode,
  }).catch(() => {});

  return {
    status: request.status,
    canExecute: request.status === "approved",
  };
}

// ── 4. Step-Up Authentication ────────────────────────────────────────────────

const stepUpTokens = new Map<string, { agentId: number; expiresAt: number }>();

export function requireStepUpAuth(agentId: number, token?: string): void {
  if (!token) {
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Step-up authentication required for this operation. Please re-authenticate.",
    });
  }

  const entry = stepUpTokens.get(token);
  if (!entry || entry.agentId !== agentId || entry.expiresAt < Date.now()) {
    stepUpTokens.delete(token ?? "");
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Step-up token invalid or expired. Please re-authenticate.",
    });
  }
}

export function issueStepUpToken(agentId: number): string {
  const token = crypto.randomBytes(32).toString("hex");
  stepUpTokens.set(token, {
    agentId,
    expiresAt: Date.now() + 5 * 60 * 1000, // 5 min validity
  });
  return token;
}

// Cleanup expired step-up tokens
setInterval(() => {
  const now = Date.now();
  for (const [key, val] of stepUpTokens) {
    if (val.expiresAt < now) stepUpTokens.delete(key);
  }
}, 60_000);

// ── 5. Privileged Session Timeout ────────────────────────────────────────────

const adminLastActivity = new Map<number, number>();
const ADMIN_IDLE_TIMEOUT = 15 * 60 * 1000; // 15 minutes

export function checkAdminSessionTimeout(agentId: number, role: string): void {
  if (role !== "admin" && role !== "super_admin") return;

  const lastActivity = adminLastActivity.get(agentId);
  if (lastActivity && Date.now() - lastActivity > ADMIN_IDLE_TIMEOUT) {
    adminLastActivity.delete(agentId);
    throw new TRPCError({
      code: "UNAUTHORIZED",
      message: "Admin session expired due to inactivity. Please re-authenticate.",
    });
  }
  adminLastActivity.set(agentId, Date.now());
}

// ── 6. Staff Velocity Detection ──────────────────────────────────────────────

interface StaffAction {
  agentId: number;
  action: string;
  amount: number;
  timestamp: number;
}

const staffActions: StaffAction[] = [];
const VELOCITY_WINDOW = 60 * 60 * 1000; // 1 hour
const MAX_REVERSALS_PER_HOUR = 5;
const MAX_HIGH_VALUE_PER_HOUR = 3;
const HIGH_VALUE_THRESHOLD = 1_000_000; // ₦1M

export async function checkStaffVelocity(
  agentId: number,
  agentCode: string,
  action: string,
  amount: number
): Promise<void> {
  const now = Date.now();

  // Clean old entries
  while (staffActions.length > 0 && now - staffActions[0].timestamp > VELOCITY_WINDOW) {
    staffActions.shift();
  }

  // Record this action
  staffActions.push({ agentId, action, amount, timestamp: now });

  // Check reversal velocity
  const agentReversals = staffActions.filter(
    a => a.agentId === agentId && a.action.includes("reversal")
  );
  if (agentReversals.length > MAX_REVERSALS_PER_HOUR) {
    publishEvent("insider.threat.velocity", `VEL-${agentId}-${now}`, {
      type: "excessive_reversals",
      agentId,
      agentCode,
      count: agentReversals.length,
      window: "1h",
      severity: "high",
    }).catch(() => {});

    dapr.publishEvent("pubsub", "insider.threat.detected", {
      type: "excessive_reversals",
      agentCode,
      count: agentReversals.length,
      severity: "high",
    }).catch(() => {});
  }

  // Check high-value transaction velocity
  const agentHighValue = staffActions.filter(
    a => a.agentId === agentId && a.amount > HIGH_VALUE_THRESHOLD
  );
  if (agentHighValue.length > MAX_HIGH_VALUE_PER_HOUR) {
    publishEvent("insider.threat.velocity", `VEL-HV-${agentId}-${now}`, {
      type: "excessive_high_value",
      agentId,
      agentCode,
      count: agentHighValue.length,
      totalAmount: agentHighValue.reduce((s, a) => s + a.amount, 0),
      window: "1h",
      severity: "critical",
    }).catch(() => {});

    dapr.publishEvent("pubsub", "insider.threat.detected", {
      type: "excessive_high_value",
      agentCode,
      totalAmount: agentHighValue.reduce((s, a) => s + a.amount, 0),
      severity: "critical",
    }).catch(() => {});
  }
}

// ── 7. Self-Transfer Blocking ────────────────────────────────────────────────

export function blockSelfTransfer(
  senderAgentId: number,
  recipientIdentifier: string,
  agentLinkedAccounts: string[]
): void {
  if (agentLinkedAccounts.includes(recipientIdentifier)) {
    throw new TRPCError({
      code: "FORBIDDEN",
      message: "Self-transfer detected: cannot transfer to your own linked account",
    });
  }
}

// ── Export all controls ──────────────────────────────────────────────────────

export const insiderThreatControls = {
  enforceSeparationOfDuties,
  getRequiredApprovals,
  createApprovalRequest,
  processApproval,
  requireStepUpAuth,
  issueStepUpToken,
  checkAdminSessionTimeout,
  checkStaffVelocity,
  blockSelfTransfer,
  APPROVAL_THRESHOLDS,
  ALWAYS_DUAL_CONTROL,
};
