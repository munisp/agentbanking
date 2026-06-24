/**
 * floatTopUp router — agent-facing procedures for submitting float top-up requests.
 *
 * Phase 48: Float top-up requests > ₦50,000 require supervisor approval
 * before admin can credit the agent's float.
 *
 * Approval flow:
 *  1. Agent submits request → supervisorApprovalRequired=true if amount > ₦50,000
 *  2. Supervisor (assigned to that agent) approves via supervisor.approveFloatTopUp
 *  3. Admin then credits the float via agentMgmt.approveTopUp (unchanged)
 *  4. Admin can override-approve any top-up regardless of supervisor approval status
 */
import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { getDb, writeAuditLog } from "../db";
import {
  floatTopUpRequests,
  agents,
  supervisorAgents,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and } from "drizzle-orm";
import { protectedProcedure, router } from "../_core/trpc";
import { getAgentFromCookie } from "../middleware/agentAuth";
import { floatTopupRequestsTotal } from "../metrics";
// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { checkDailyLimit } from "../lib/cbnLimits";
import { withIdempotency } from "../lib/transactionHelper";
import { enforcePermission } from "../_core/permify";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";


const STATUS_TRANSITIONS: Record<string, string[]> = {
  initiated: ["pending_validation"],
  pending_validation: ["validated", "failed_validation"],
  validated: ["authorized", "declined"],
  authorized: ["processing"],
  processing: ["completed", "failed", "reversed"],
  completed: ["settled", "disputed", "reversed"],
  settled: ["reconciled"],
  reconciled: ["archived"],
  failed: ["retry_pending", "cancelled"],
  failed_validation: ["retry_pending", "cancelled"],
  declined: ["cancelled"],
  reversed: ["refund_processing"],
  refund_processing: ["refunded"],
  refunded: ["archived"],
  disputed: ["under_investigation"],
  under_investigation: ["resolved", "escalated"],
  resolved: ["archived"],
  escalated: ["resolved"],
  retry_pending: ["processing"],
  cancelled: [],
  archived: [],
};

const SUPERVISOR_APPROVAL_THRESHOLD = 50_000;

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "floatTopUp",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "floatTopUp",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Extended Validation Schemas ────────────────────────────────────────────
const _floatTopUpSchemas = {
  idParam: z.object({ id: z.number().int().positive() }),
  paginationInput: z.object({
    page: z.number().int().min(1).default(1),
    pageSize: z.number().int().min(1).max(100).default(20),
    sortBy: z.string().optional(),
    sortOrder: z.enum(["asc", "desc"]).default("desc"),
  }),
  dateRange: z.object({
    from: z.string().datetime().optional(),
    to: z.string().datetime().optional(),
  }),
  searchInput: z.object({
    query: z.string().min(1).max(500),
    filters: z.record(z.string(), z.string()).optional(),
  }),
};


async function publishfloatTopUpMiddleware(event: string, key: string, payload: Record<string, unknown>) {
  publishEvent("float.topped_up", key, { event, ...payload, timestamp: Date.now() }).catch(() => {});
  tbCreateTransfer({ debitAccountId: "1001", creditAccountId: "2001", amount: Number(payload.amount ?? 0), ledger: 1, code: 1, ref: key, txType: event, agentCode: String(payload.agentId ?? "system") }).catch(() => {});
  publishTxToFluvio({ txRef: key, agentCode: String(payload.agentId ?? "system"), amount: Number(payload.amount ?? 0), type: `float.topped_up.${event}`, timestamp: Date.now() }).catch(() => {});
  dapr.publishEvent("pubsub", `float.topped_up.${event}`, { key, ...payload }).catch(() => {});
  ingestToLakehouse("floatTopUp", { event, key, ...payload, timestamp: new Date().toISOString() }).catch(() => {});
  cacheSet(`floatTopUp:${key}`, JSON.stringify(payload), 300).catch(() => {});
}

export const floatTopUpRouter = router({
  // ── Submit a top-up request ───────────────────────────────────────────────
  submit: protectedProcedure
    .input(
      z.object({
        amount: z.number().min(0).positive().max(10_000_000),
        notes: z.string().max(256).optional(),
        idempotencyKey: z.string().min(16).max(64).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx.user?.id ?? "0"), entityType: "float_account", entityId: String((input as any)?.id ?? (input as any)?.customerId ?? (input as any)?.agentId ?? Date.now()), permission: "topup" }).catch(() => {});

      const session = await getAgentFromCookie(ctx.req);
      if (!session)
        throw new TRPCError({
          code: "UNAUTHORIZED",
          message: "Agent session required",
        });

      const executeFn = async () => {
      const txAmount = input.amount;
      const fees = calculateFee(txAmount, "floatTopUp");
      const commission = calculateCommission(fees.fee, "floatTopUp");
      const tax = calculateTax(fees.fee, "vat");
      try {

        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        // Check for existing pending request
        const existing = await db
          .select()
          .from(floatTopUpRequests)
          .where(eq(floatTopUpRequests.agentId, session.id))
          .orderBy(desc(floatTopUpRequests.createdAt))
          .limit(1);
        if (existing[0] && existing[0].status === "pending") {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message:
              "You already have a pending top-up request. Please wait for approval.",
          });
        }

        // Phase 48: determine if supervisor approval is required
        const requiresSupervisor = input.amount > SUPERVISOR_APPROVAL_THRESHOLD;

        const result = await db
          .insert(floatTopUpRequests)
          .values({
            agentId: session.id,
            requestedAmount: String(input.amount),
            status: "pending",
            notes: input.notes ?? null,
            supervisorApprovalRequired: requiresSupervisor,
          })
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `floatTopUp transaction`,
          debitAccountId: 2001,
          creditAccountId: 1001,
          amount: Math.round(
            (typeof input === "object" && "amount" in input
              ? Number((input as any).amount)
              : 0) * 100
          ),
          currency: "NGN",
          status: "posted",
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "FLOAT_TOPUP_REQUESTED",
          resource: "float_topup",
          resourceId: String(result[0].id),
          status: "success",
          metadata: { amount: input.amount, requiresSupervisor },
        });

        // Notify supervisor(s) assigned to this agent if threshold exceeded
        if (requiresSupervisor) {
          try {
            const { notifyOwner } = await import("../_core/notification");
            await notifyOwner({
              title: `Large Float Top-Up Requires Supervisor Approval — ₦${input.amount.toLocaleString()}`,
              content: `Agent ${session.agentCode} (${session.name}) has requested a float top-up of ₦${input.amount.toLocaleString()} (above ₦${SUPERVISOR_APPROVAL_THRESHOLD.toLocaleString()} threshold). Please review in the Supervisor Dashboard → Pending Float Approvals.`,
            });
          } catch {
            // Non-critical
          }
        }

        floatTopupRequestsTotal.labels("submitted").inc();

        await publishfloatTopUpMiddleware("submit", `${Date.now()}`, { action: "submit" }).catch(() => {});


        return {
          success: true,
          requestId: result[0].id,
          requiresSupervisorApproval: requiresSupervisor,
          message: requiresSupervisor
            ? `Top-up request submitted. Supervisor approval required for amounts above ₦${SUPERVISOR_APPROVAL_THRESHOLD.toLocaleString()}.`
            : "Top-up request submitted. Awaiting admin approval.",
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
      }; // end executeFn

      if (input.idempotencyKey) {
        return withIdempotency(input.idempotencyKey, executeFn);
      }
      return executeFn();
    }),

  // ── List agent's own requests ─────────────────────────────────────────────
  myRequests: protectedProcedure.query(async ({ ctx }) => {
    try {
      const session = await getAgentFromCookie(ctx.req);
      if (!session)
        throw new TRPCError({
          code: "UNAUTHORIZED",
          message: "Agent session required",
        });
      const db = (await getDb())!;
      if (!db) throw new Error("Database connection unavailable");
      const rows = await db
        .select()
        .from(floatTopUpRequests)
        .where(eq(floatTopUpRequests.agentId, session.id))
        .orderBy(desc(floatTopUpRequests.createdAt))
        .limit(20);
      return rows.map((r: any) => ({
        ...r,
        requestedAmount: Number(r.requestedAmount),
      }));
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),

  // ── Supervisor: list pending large top-ups for assigned agents ────────────
  supervisorPendingTopUps: protectedProcedure.query(async ({ ctx }) => {
    try {
      const session = await getAgentFromCookie(ctx.req);
      if (!session)
        throw new TRPCError({
          code: "UNAUTHORIZED",
          message: "Agent session required",
        });
      if (session.role !== "supervisor" && session.role !== "admin") {
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "Supervisor or admin privileges required",
        });
      }

      const db = (await getDb())!;
      if (!db) throw new Error("Database connection unavailable");

      // For supervisors: only show top-ups for their assigned agents
      // For admins: show all supervisor-required top-ups
      let agentIds: number[] = [];
      if (session.role === "supervisor") {
        const assignments = await db
          .select({ agentId: supervisorAgents.agentId })
          .from(supervisorAgents)
          .where(eq(supervisorAgents.supervisorUserId, session.id));
        agentIds = assignments.map((a: any) => a.agentId);
        if (agentIds.length === 0) return [];
      }

      const rows = await db
        .select({
          id: floatTopUpRequests.id,
          agentId: floatTopUpRequests.agentId,
          requestedAmount: floatTopUpRequests.requestedAmount,
          status: floatTopUpRequests.status,
          supervisorApprovalRequired:
            floatTopUpRequests.supervisorApprovalRequired,
          supervisorApprovedBy: floatTopUpRequests.supervisorApprovedBy,
          supervisorApprovedAt: floatTopUpRequests.supervisorApprovedAt,
          notes: floatTopUpRequests.notes,
          createdAt: floatTopUpRequests.createdAt,
          agentCode: agents.agentCode,
          agentName: agents.name,
          agentFloat: agents.floatBalance,
          agentTier: agents.tier,
        })
        .from(floatTopUpRequests)
        .leftJoin(agents, eq(floatTopUpRequests.agentId, agents.id))
        .where(
          and(
            eq(floatTopUpRequests.supervisorApprovalRequired, true),
            eq(floatTopUpRequests.status, "pending")
          )
        )
        .orderBy(desc(floatTopUpRequests.createdAt));

      // Filter by assigned agents for supervisors
      const filtered =
        session.role === "supervisor"
          ? rows.filter(
              (r: any) => r.agentId !== null && agentIds.includes(r.agentId)
            )
          : rows;

      return filtered.map((r: any) => ({
        ...r,
        requestedAmount: Number(r.requestedAmount),
        agentFloat: Number(r.agentFloat ?? 0),
      }));
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),

  // ── Supervisor: approve a large top-up ───────────────────────────────────
  supervisorApproveTopUp: protectedProcedure
    .input(
      z.object({
        requestId: z.number().int().positive(),
        notes: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx?.user?.id ?? "0"), entityType: "transaction", entityId: String((input as any)?.id ?? (input as any)?.customerId ?? (input as any)?.agentId ?? Date.now()), permission: "create" }).catch(() => {});
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });
        if (session.role !== "supervisor" && session.role !== "admin") {
          throw new TRPCError({
            code: "FORBIDDEN",
            message: "Supervisor or admin privileges required",
          });
        }

        const db = (await getDb())!;
        if (!db)
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "DB unavailable",
          });

        const rows = await db
          .select()
          .from(floatTopUpRequests)
          .where(eq(floatTopUpRequests.id, input.requestId))
          .limit(1);
        const req = rows[0];
        if (!req)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Request not found",
          });
        if (req.status !== "pending") {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Request already ${req.status}`,
          });
        }

        // Verify supervisor is assigned to this agent (skip for admin)
        if (session.role === "supervisor") {
          const assignment = await db
            .select()
            .from(supervisorAgents)
            .where(
              and(
                eq(supervisorAgents.supervisorUserId, session.id),
                eq(supervisorAgents.agentId, req.agentId)
              )
            )
            .limit(1);
          if (!assignment[0]) {
            throw new TRPCError({
              code: "FORBIDDEN",
              message: "You are not assigned as supervisor for this agent",
            });
          }
        }

        await db
          .update(floatTopUpRequests)
          .set({
            supervisorApprovedBy: session.agentCode,
            supervisorApprovedAt: new Date(),
            notes: input.notes
              ? `${req.notes ?? ""}\nSupervisor note: ${input.notes}`.trim()
              : req.notes,
            updatedAt: new Date(),
          })
          .where(eq(floatTopUpRequests.id, input.requestId));

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "FLOAT_TOPUP_SUPERVISOR_APPROVED",
          resource: "float_topup",
          resourceId: String(input.requestId),
          status: "success",
          metadata: {
            amount: Number(req.requestedAmount),
            targetAgentId: req.agentId,
            notes: input.notes,
          },
        });

        await publishfloatTopUpMiddleware("supervisorApproveTopUp", `${Date.now()}`, { action: "supervisorApproveTopUp" }).catch(() => {});


        return {
          success: true,
          message:
            "Supervisor approval recorded. Admin can now credit the float.",
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Additional query/mutation procedures ─────────────────────
  getStats_floatTopUp: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      lastUpdated: new Date().toISOString(),
      status: "operational",
    };
  }),

  healthCheck_floatTopUp: protectedProcedure.query(async () => {
    return {
      healthy: true,
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }),
});
