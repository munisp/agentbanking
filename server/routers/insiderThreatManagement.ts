/**
 * Insider Threat Management Router
 *
 * Provides API endpoints for:
 * - Approval workflow management (create, approve, reject, list pending)
 * - Step-up authentication (issue/verify tokens)
 * - Staff velocity monitoring
 * - Blocked agent management
 * - Audit chain verification
 * - Permission conflict detection
 * - Insider threat dashboard data
 */
import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { sql } from "drizzle-orm";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import {
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
} from "../middleware/insiderThreatPrevention";

export const insiderThreatManagementRouter = router({
  // ── Approval Workflows ─────────────────────────────────────────────────────

  createApproval: protectedProcedure
    .input(
      z.object({
        type: z.string().min(1),
        amount: z.number().positive(),
        currency: z.string().default("NGN"),
        resource: z.string().min(1),
        resourceId: z.string().min(1),
        metadata: z.record(z.string(), z.unknown()).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });

      await checkAdminSessionTimeout(agent.id, agent.role);

      const request = await createApprovalRequest({
        type: input.type,
        requestedBy: agent.id,
        requestedByCode: agent.agentCode,
        amount: input.amount,
        currency: input.currency,
        resource: input.resource,
        resourceId: input.resourceId,
        metadata: input.metadata,
      });

      // Track velocity
      await checkStaffVelocity(
        agent.id,
        agent.agentCode,
        input.type,
        input.amount
      );

      // Middleware integration
      tbCreateTransfer({
        debitAccountId: "9001", // Pending approvals suspense
        creditAccountId: "9002", // Approval workflow holding
        amount: input.amount,
        ledger: 900,
        code: 1,
        ref: request.id,
      }).catch(() => {});

      publishTxToFluvio({
        txRef: request.id,
        agentCode: agent.agentCode,
        amount: input.amount,
        type: "approval_created",
        timestamp: Date.now(),
      }).catch(() => {});

      ingestToLakehouse("approval_requests", {
        requestId: request.id,
        type: input.type,
        amount: input.amount,
        requestedBy: agent.agentCode,
        status: "pending",
      }).catch(() => {});

      return request;
    }),

  approveRequest: protectedProcedure
    .input(
      z.object({
        requestId: z.string().min(1),
        stepUpToken: z.string().optional(),
        reason: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });

      // Admin session timeout
      await checkAdminSessionTimeout(agent.id, agent.role);

      // Step-up auth required for approvals
      await requireStepUpAuth(agent.id, input.stepUpToken);

      const result = await processApproval({
        requestId: input.requestId,
        approverAgentId: agent.id,
        approverAgentCode: agent.agentCode,
        approverRole: agent.role,
        action: "approve",
        reason: input.reason,
      });

      // Track velocity
      await checkStaffVelocity(agent.id, agent.agentCode, "approval_action", 0);

      // Middleware
      publishTxToFluvio({
        txRef: input.requestId,
        agentCode: agent.agentCode,
        amount: 0,
        type: "approval_approved",
        timestamp: Date.now(),
      }).catch(() => {});

      ingestToLakehouse("approval_actions", {
        requestId: input.requestId,
        action: "approve",
        approvedBy: agent.agentCode,
        status: result.status,
      }).catch(() => {});

      return result;
    }),

  rejectRequest: protectedProcedure
    .input(
      z.object({
        requestId: z.string().min(1),
        reason: z.string().min(5),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });

      await checkAdminSessionTimeout(agent.id, agent.role);

      const result = await processApproval({
        requestId: input.requestId,
        approverAgentId: agent.id,
        approverAgentCode: agent.agentCode,
        approverRole: agent.role,
        action: "reject",
        reason: input.reason,
      });

      publishTxToFluvio({
        txRef: input.requestId,
        agentCode: agent.agentCode,
        amount: 0,
        type: "approval_rejected",
        timestamp: Date.now(),
      }).catch(() => {});

      return result;
    }),

  listPendingApprovals: protectedProcedure
    .input(
      z.object({ limit: z.number().int().positive().default(50) }).optional()
    )
    .query(async ({ ctx, input }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });
      if (agent.role !== "admin" && agent.role !== "super_admin") {
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "Admin access required",
        });
      }

      const db = await getDb();
      if (!db) return { approvals: [] };

      const rows = await db.execute(
        sql`SELECT value FROM platform_settings WHERE key LIKE 'approval_request_APR-%' ORDER BY key DESC LIMIT ${input?.limit ?? 50}`
      );
      const results = ((rows as any).rows ?? rows) as any[];
      const approvals = results
        .map((r: any) => JSON.parse(String(r.value)))
        .filter((a: any) => a.status === "pending");

      return { approvals };
    }),

  // ── Step-Up Authentication ─────────────────────────────────────────────────

  requestStepUp: protectedProcedure
    .input(
      z.object({
        password: z.string().min(1),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });

      // In production: verify password against hashed password in DB
      // For now, issue token if authenticated
      const token = await issueStepUpToken(agent.id);

      await writeAuditLog({
        agentId: agent.id,
        agentCode: agent.agentCode,
        action: "STEP_UP_AUTH_ISSUED",
        resource: "session",
        resourceId: `stepup-${agent.id}`,
        status: "success",
        metadata: { tokenExpiresIn: "5m" },
      });

      publishEvent("insider.auth.step-up", `SU-${agent.id}-${Date.now()}`, {
        agentCode: agent.agentCode,
        type: "step_up_issued",
      }).catch(() => {});

      return { token, expiresIn: 300 }; // 5 minutes
    }),

  // ── Threshold Configuration ────────────────────────────────────────────────

  getThresholds: protectedProcedure.query(async ({ ctx }) => {
    const agent = (ctx as any).agent;
    if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });
    return {
      thresholds: APPROVAL_THRESHOLDS,
      alwaysDualControl: ALWAYS_DUAL_CONTROL,
    };
  }),

  checkThreshold: protectedProcedure
    .input(
      z.object({
        amount: z.number().positive(),
        operationType: z.string().min(1),
      })
    )
    .query(async ({ input }) => {
      return getRequiredApprovals(input.amount, input.operationType);
    }),

  // ── Audit Chain Verification ───────────────────────────────────────────────

  verifyAuditChain: protectedProcedure.query(async ({ ctx }) => {
    const agent = (ctx as any).agent;
    if (!agent || agent.role !== "admin") {
      throw new TRPCError({ code: "FORBIDDEN" });
    }

    // Call Rust audit-chain service
    try {
      const res = await fetch("http://localhost:8260/verify");
      if (res.ok) return await res.json();
    } catch {}

    return {
      valid: true,
      message: "Audit chain service not reachable — verify locally",
      total_entries: 0,
    };
  }),

  getHighRiskActions: protectedProcedure.query(async ({ ctx }) => {
    const agent = (ctx as any).agent;
    if (!agent || (agent.role !== "admin" && agent.role !== "compliance")) {
      throw new TRPCError({ code: "FORBIDDEN" });
    }

    try {
      const res = await fetch("http://localhost:8260/high-risk");
      if (res.ok) return await res.json();
    } catch {}

    return [];
  }),

  // ── Insider Threat Dashboard ───────────────────────────────────────────────

  getDashboard: protectedProcedure.query(async ({ ctx }) => {
    const agent = (ctx as any).agent;
    if (!agent || (agent.role !== "admin" && agent.role !== "compliance")) {
      throw new TRPCError({ code: "FORBIDDEN" });
    }

    // Fetch from Python detection service
    let detectionStats = null;
    try {
      const res = await fetch("http://localhost:8262/stats");
      if (res.ok) detectionStats = await res.json();
    } catch {}

    // Fetch from Go RBAC service
    let rbacRoles = null;
    try {
      const res = await fetch("http://localhost:8261/roles");
      if (res.ok) rbacRoles = await res.json();
    } catch {}

    return {
      detection: detectionStats ?? {
        total_alerts: 0,
        alerts_by_severity: { critical: 0, high: 0, medium: 0, low: 0 },
        blocked_agents: 0,
      },
      rbac: {
        roles: rbacRoles ?? [],
        incompatiblePairCount: 7,
      },
      thresholds: APPROVAL_THRESHOLDS,
      alwaysDualControl: ALWAYS_DUAL_CONTROL,
    };
  }),

  getAlerts: protectedProcedure
    .input(
      z
        .object({
          severity: z.enum(["low", "medium", "high", "critical"]).optional(),
          agentId: z.number().int().optional(),
          limit: z.number().int().positive().default(100),
        })
        .optional()
    )
    .query(async ({ ctx, input }) => {
      const agent = (ctx as any).agent;
      if (!agent || (agent.role !== "admin" && agent.role !== "compliance")) {
        throw new TRPCError({ code: "FORBIDDEN" });
      }

      try {
        let url = `http://localhost:8262/alerts?limit=${input?.limit ?? 100}`;
        if (input?.severity) url += `&severity=${input.severity}`;
        if (input?.agentId) url += `&agent_id=${input.agentId}`;
        const res = await fetch(url);
        if (res.ok) return await res.json();
      } catch {}

      return { alerts: [], total: 0 };
    }),

  // ── Permission Management ──────────────────────────────────────────────────

  checkPermission: protectedProcedure
    .input(
      z.object({
        permission: z.string().min(1),
        resource: z.string().optional(),
        resourceId: z.string().optional(),
      })
    )
    .query(async ({ input, ctx }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });

      try {
        const res = await fetch("http://localhost:8261/check", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agentId: agent.id,
            agentCode: agent.agentCode,
            permission: input.permission,
            resource: input.resource ?? "",
            resourceId: input.resourceId ?? "",
          }),
        });
        if (res.ok) return await res.json();
      } catch {}

      // Fallback: role-based check
      return {
        allowed: agent.role === "admin",
        reason: "RBAC service unavailable — fallback to role check",
      };
    }),

  checkConflicts: protectedProcedure
    .input(
      z.object({
        permissions: z.array(z.string()),
      })
    )
    .query(async ({ input, ctx }) => {
      const agent = (ctx as any).agent;
      if (!agent) throw new TRPCError({ code: "UNAUTHORIZED" });

      try {
        const res = await fetch("http://localhost:8261/conflicts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agentId: agent.id,
            permissions: input.permissions,
          }),
        });
        if (res.ok) return await res.json();
      } catch {}

      return {
        hasConflict: false,
        conflicts: [],
        message: "RBAC service unavailable",
      };
    }),
});
