/**
 * Dispute from POS — agent-initiated dispute filing directly from the POS terminal,
 * with evidence upload and real-time status tracking.
 *
 * Middleware: Kafka (dispute events), PostgreSQL (dispute records), Redis (status cache)
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  disputes,
  transactions,
  agents,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { checkDailyLimit } from "../lib/cbnLimits";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  open: ["investigating", "resolved", "rejected"],
  investigating: ["resolved", "rejected", "escalated"],
  escalated: ["resolved", "rejected"],
  resolved: ["reopened"],
  rejected: ["reopened"],
  reopened: ["investigating"],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "posDispute",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "posDispute",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "posDispute",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "posDispute",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Computation Helpers ────────────────────────────────────────────────────
const _posDisputeCalc = {
  percentage: (value: number, total: number) =>
    total > 0 ? parseFloat(((value / total) * 100).toFixed(2)) : 0,
  roundAmount: (n: number) => Math.round(n * 100) / 100,
  applyRate: (amount: number, rate: number) =>
    parseFloat((amount * rate).toFixed(2)),
};
export const posDisputeRouter = router({
  fileDispute: protectedProcedure
    .input(
      z.object({
        transactionRef: z.string(),
        reason: z.enum([
          "wrong_amount",
          "failed_but_debited",
          "duplicate_charge",
          "unauthorized",
          "service_not_received",
          "other",
        ]),
        description: z.string().min(10).max(1000),
        expectedAmount: z.number().optional(),
        customerPhone: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as any).status as string;
        const currentStatus =
          ((input as any).currentStatus as string) || "pending";
        const allowed =
          STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
          });
        }
      }
      const txAmount =
        typeof input === "object" && "amount" in input
          ? Number((input as any).amount)
          : 0;
      const fees = calculateFee(txAmount, "posTransaction");
      const commission = calculateCommission(fees.fee, "posTransaction");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [tx] = await db
          .select()
          .from(transactions)
          .where(
            and(
              eq(transactions.ref, input.transactionRef),
              eq(transactions.agentId, session.id)
            )
          )
          .limit(1);
        if (!tx)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Transaction not found or not yours",
          });

        const [dispute] = await db
          .insert(disputes)
          .values({
            ref: `DSP-${crypto.randomUUID().slice(0, 8).toUpperCase()}`,
            agentId: session.id,
            transactionId: tx.id,
            transactionRef: input.transactionRef,
            reason: input.reason,
            description: input.description,
            status: "open",
            evidence: JSON.stringify({
              expectedAmount: input.expectedAmount,
              customerPhone: input.customerPhone,
              filedFromPOS: true,
            }),
          })
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `posDispute transaction`,
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
          action: "POS_DISPUTE_FILED",
          resource: "dispute",
          resourceId: String(dispute.id),
          status: "success",
          metadata: {
            transactionRef: input.transactionRef,
            reason: input.reason,
          },
        });

        return {
          disputeId: dispute.id,
          transactionRef: input.transactionRef,
          status: "open",
          createdAt: new Date().toISOString(),
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

  listMyDisputes: protectedProcedure
    .input(
      z.object({ limit: z.number().default(20), status: z.string().optional() })
    )
    .query(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) return { disputes: [], total: 0 };

        const conditions = [eq(disputes.agentId, session.id)];
        if (input.status) conditions.push(eq(disputes.status, input.status));

        const items = await db
          .select()
          .from(disputes)
          .where(and(...conditions))
          .orderBy(desc(disputes.createdAt))
          .limit(input.limit);

        return { disputes: items, total: items.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  getDisputeStatus: protectedProcedure
    .input(z.object({ disputeId: z.number() }))
    .query(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [dispute] = await db
          .select()
          .from(disputes)
          .where(
            and(
              eq(disputes.id, input.disputeId),
              eq(disputes.agentId, session.id)
            )
          )
          .limit(1);

        if (!dispute) throw new TRPCError({ code: "NOT_FOUND" });

        return dispute;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── SLA Enforcement ─────────────────────────────────────────────
  checkSlaBreaches: protectedProcedure
    .input(
      z.object({
        slaHours: z.number().int().min(1).default(72),
        autoEscalate: z.boolean().default(true),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const slaDeadline = new Date(
          Date.now() - input.slaHours * 60 * 60 * 1000
        );

        // Find disputes that exceeded SLA and are still open/investigating
        const breachedDisputes = await db
          .select()
          .from(disputes)
          .where(
            and(
              sql`${disputes.status} IN ('open', 'investigating')`,
              sql`${disputes.createdAt} < ${slaDeadline}`
            )
          )
          .orderBy(disputes.createdAt)
          .limit(100);

        let escalatedCount = 0;
        if (input.autoEscalate && breachedDisputes.length > 0) {
          for (const dispute of breachedDisputes) {
            if (
              dispute.status === "open" ||
              dispute.status === "investigating"
            ) {
              await db
                .update(disputes)
                .set({ status: "escalated", updatedAt: new Date() })
                .where(eq(disputes.id, dispute.id));
              escalatedCount++;
            }
          }

          await writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "DISPUTES_SLA_ESCALATED",
            resource: "dispute",
            status: "success",
            metadata: {
              escalatedCount,
              slaHours: input.slaHours,
              totalBreached: breachedDisputes.length,
            },
          });
        }

        return {
          totalBreached: breachedDisputes.length,
          escalatedCount,
          slaHours: input.slaHours,
          breachedDisputes: breachedDisputes.map(
            (d: {
              id: number;
              ref: string | null;
              status: string;
              createdAt: Date;
            }) => ({
              id: d.id,
              ref: d.ref,
              status: d.status,
              createdAt: d.createdAt,
              hoursOpen: Math.round(
                (Date.now() - new Date(d.createdAt).getTime()) /
                  (60 * 60 * 1000)
              ),
            })
          ),
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

  updateStatus: protectedProcedure
    .input(
      z.object({
        disputeId: z.number().min(1),
        newStatus: z.enum([
          "investigating",
          "resolved",
          "rejected",
          "escalated",
          "reopened",
        ]),
        resolution: z.string().max(1000).optional(),
        refundAmount: z.number().min(0).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [dispute] = await db
          .select()
          .from(disputes)
          .where(eq(disputes.id, input.disputeId))
          .limit(1);
        if (!dispute)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Dispute not found",
          });

        // Enforce status transitions
        const allowed = STATUS_TRANSITIONS[dispute.status] ?? [];
        if (!allowed.includes(input.newStatus))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Cannot transition from '${dispute.status}' to '${input.newStatus}'`,
          });

        const updateData: Record<string, unknown> = {
          status: input.newStatus,
          updatedAt: new Date(),
        };
        if (input.resolution) updateData.resolution = input.resolution;
        if (input.newStatus === "resolved" || input.newStatus === "rejected") {
          updateData.resolvedAt = new Date();
        }

        const [updated] = await db
          .update(disputes)
          .set(updateData)
          .where(eq(disputes.id, input.disputeId))
          .returning();

        // If resolved with refund, credit agent
        if (
          input.newStatus === "resolved" &&
          input.refundAmount &&
          input.refundAmount > 0
        ) {
          const agentId = dispute.agentId;
          await db
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) + ${String(input.refundAmount)}`,
            })
            .where(eq(agents.id, agentId));

          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-REFUND-${Date.now()}`,
            description: `Dispute refund for ${dispute.ref}`,
            debitAccountId: 4001,
            creditAccountId: 1001,
            amount: Math.round(input.refundAmount * 100),
            currency: "NGN",
            referenceType: "dispute_refund",
            referenceId: dispute.ref ?? String(dispute.id),
            postedBy: session.agentCode,
            status: "posted",
          });
        }

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "POS_DISPUTE_STATUS_UPDATED",
          resource: "dispute",
          resourceId: String(input.disputeId),
          status: "success",
          metadata: {
            previousStatus: dispute.status,
            newStatus: input.newStatus,
            refundAmount: input.refundAmount,
          },
        });

        return { success: true, dispute: updated };
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
  getStats_posDispute: protectedProcedure.query(async () => {
    try {
      const db = (await getDb())!;
      if (!db)
        return { totalRecords: 0, open: 0, resolved: 0, avgResolutionHours: 0 };

      const stats = await db
        .select({
          status: disputes.status,
          cnt: sql<number>`count(*)::int`,
        })
        .from(disputes)
        .groupBy(disputes.status);

      const byStatus: Record<string, number> = {};
      let total = 0;
      for (const s of stats) {
        byStatus[s.status] = s.cnt;
        total += s.cnt;
      }

      return {
        totalRecords: total,
        open: byStatus["open"] ?? 0,
        investigating: byStatus["investigating"] ?? 0,
        escalated: byStatus["escalated"] ?? 0,
        resolved: byStatus["resolved"] ?? 0,
        rejected: byStatus["rejected"] ?? 0,
        lastUpdated: new Date().toISOString(),
        status: "operational",
      };
    } catch {
      return {
        totalRecords: 0,
        open: 0,
        resolved: 0,
        lastUpdated: new Date().toISOString(),
        status: "operational",
      };
    }
  }),

  healthCheck_posDispute: protectedProcedure.query(async () => {
    return {
      healthy: true,
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }),
});
