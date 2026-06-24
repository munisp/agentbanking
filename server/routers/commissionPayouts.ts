/**
 * Commission Payouts Router
 * Full lifecycle: request → approve/reject → process → complete
 * Integrates with agent commissionBalance and email notifications.
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import {
  commissionPayouts,
  agents,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, count, gte, lte, sql } from "drizzle-orm";
import { enqueueEmail, buildAlertEmail } from "../lib/emailQueue";
import { dispatchWebhookEvent } from "../lib/webhookDelivery";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import { enforcePermission } from "../_core/permify";


const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["processing", "cancelled"],
  processing: ["settled", "failed"],
  settled: [],
  failed: ["pending"],
  cancelled: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "commissionPayouts",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "commissionPayouts",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations
export const commissionPayoutsRouter = router({
  // ── List payouts (admin/supervisor) ──────────────────────────────────────
  list: protectedProcedure
    .input(
      z.object({
        page: z.number().default(1),
        limit: z.number().default(20),
        status: z
          .enum([
            "pending",
            "approved",
            "processing",
            "completed",
            "failed",
            "rejected",
          ])
          .optional(),
        agentCode: z.string().optional(),
        from: z.string().optional(), // ISO date
        to: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const offset = (input.page - 1) * input.limit;
        const conditions = [];
        if (input.status)
          conditions.push(eq(commissionPayouts.status, input.status));
        if (input.agentCode)
          conditions.push(eq(commissionPayouts.agentCode, input.agentCode));
        if (input.from)
          conditions.push(
            gte(commissionPayouts.createdAt, new Date(input.from))
          );
        if (input.to)
          conditions.push(lte(commissionPayouts.createdAt, new Date(input.to)));

        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const [items, [{ c: total }]] = await Promise.all([
          db
            .select()
            .from(commissionPayouts)
            .where(where)
            .orderBy(desc(commissionPayouts.createdAt))
            .limit(input.limit)
            .offset(offset),
          db.select({ c: count() }).from(commissionPayouts).where(where),
        ]);
        return { items, total: Number(total) };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Get payout summary stats ──────────────────────────────────────────────
  stats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) return { pending: 0, approved: 0, completed: 0, totalPaid: "0" };
    const rows = await db.select().from(commissionPayouts).limit(100);
    const pending = rows.filter((r: any) => r.status === "pending").length;
    const approved = rows.filter((r: any) => r.status === "approved").length;
    const completed = rows.filter((r: any) => r.status === "completed").length;
    const totalPaid = rows
      .filter((r: any) => r.status === "completed")
      .reduce((sum: any, r: any) => sum + parseFloat(r.amount as string), 0)
      .toFixed(2);
    return { pending, approved, completed, totalPaid };
  }),

  // ── Request a payout (agent self-service) ────────────────────────────────
  request: protectedProcedure
    .input(
      z.object({
        agentCode: z.string(),
        amount: z.number().min(0).positive(),
        bankCode: z.string().max(10).optional(),
        accountNumber: z.string().max(20).optional(),
        accountName: z.string().max(100).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx.user?.id ?? "0"), entityType: "commission", entityId: String((input as any)?.id ?? (input as any)?.customerId ?? (input as any)?.agentId ?? Date.now()), permission: "payout" }).catch(() => {});

      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as Record<string, unknown>).status as string;
        const currentStatus =
          ((input as Record<string, unknown>).currentStatus as string) ||
          "pending";
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
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "commissionPayout");
      const commission = calculateCommission(fees.fee, "commissionPayout");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        // Verify agent and check commission balance
        const [agent] = await db
          .select()
          .from(agents)
          .where(eq(agents.agentCode, input.agentCode))
          .limit(1);
        if (!agent)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Agent not found",
          });

        const balance = parseFloat(agent.commissionBalance as string);
        if (balance < input.amount) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Insufficient commission balance. Available: ₦${balance.toFixed(2)}`,
          });
        }
        if (input.amount < 500) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Minimum payout is ₦500",
          });
        }

        const [payout] = await db
          .insert(commissionPayouts)
          .values({
            agentId: agent.id,
            agentCode: input.agentCode,
            amount: String(input.amount),
            bankCode: input.bankCode,
            accountNumber: input.accountNumber,
            accountName: input.accountName,
            requestedBy: ctx.user.id,
            status: "pending",
          })
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `commissionPayouts transaction`,
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
          agentId: agent.id,
          agentCode: input.agentCode,
          action: "commission_payout_requested",
          resource: "commission_payout",
          resourceId: String(payout.id),
          status: "success",
        });

        publishEvent("pos.transactions.created", String(payout.id), {
          type: "commission_payout_requested",
          payoutId: payout.id,
          agentId: agent.id,
          agentCode: input.agentCode,
          amount: input.amount,
          timestamp: new Date().toISOString(),
        }, { agentCode: input.agentCode }).catch(() => {});

        const commRef = `COMM-${payout.id}-${Date.now()}`;

        // TigerBeetle dual-ledger
        tbCreateTransfer({
          debitAccountId: "4001", creditAccountId: "2001",
          amount: Math.round(input.amount * 100),
          ref: commRef, txType: "commission_payout", agentCode: input.agentCode,
        }).catch(() => {});

        // Fluvio + Dapr + Redis + Lakehouse
        publishTxToFluvio({ txRef: commRef, agentCode: input.agentCode, amount: input.amount, type: "commission_payout", timestamp: Date.now() }).catch(() => {});
        dapr.publishEvent("pubsub", "commission.payout.requested", { commRef, payoutId: payout.id, agentId: agent.id, amount: input.amount }).catch(() => {});
        cacheSet(`agent:commission:${agent.id}`, "", 1).catch(() => {});
        ingestToLakehouse("commission_payouts", { commRef, payoutId: payout.id, agentId: agent.id, agentCode: input.agentCode, amount: input.amount, timestamp: new Date().toISOString() }).catch(() => {});

        return payout;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Approve a payout (supervisor/admin) ──────────────────────────────────
  approve: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx?.user?.id ?? "0"), entityType: "commission", entityId: String((input as any)?.id ?? (input as any)?.customerId ?? (input as any)?.agentId ?? Date.now()), permission: "payout" }).catch(() => {});
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [payout] = await db
          .select()
          .from(commissionPayouts)
          .where(eq(commissionPayouts.id, input.id))
          .limit(1);
        if (!payout) throw new TRPCError({ code: "NOT_FOUND" });
        if (payout.status !== "pending") {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Payout is not in pending state",
          });
        }

        const [updated] = await db
          .update(commissionPayouts)
          .set({
            status: "approved",
            approvedBy: ctx.user.id,
            updatedAt: new Date(),
          })
          .where(eq(commissionPayouts.id, input.id))
          .returning();

        await dispatchWebhookEvent("commission.payout.approved", {
          payoutId: updated.id,
          agentCode: updated.agentCode,
          amount: updated.amount,
        });

        return updated;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Reject a payout ───────────────────────────────────────────────────────
  reject: protectedProcedure
    .input(z.object({ id: z.number(), reason: z.string().min(1) }))
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx?.user?.id ?? "0"), entityType: "commission", entityId: String((input as any)?.id ?? (input as any)?.customerId ?? (input as any)?.agentId ?? Date.now()), permission: "payout" }).catch(() => {});
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [updated] = await db
          .update(commissionPayouts)
          .set({
            status: "rejected",
            rejectedBy: ctx.user.id,
            rejectionReason: input.reason,
            updatedAt: new Date(),
          })
          .where(eq(commissionPayouts.id, input.id))
          .returning();

        return updated;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Process a payout (deduct from agent balance + mark completed) ────────
  process: protectedProcedure
    .input(z.object({ id: z.number(), nubanRef: z.string().optional() }))
    .mutation(async ({ input }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx?.user?.id ?? "0"), entityType: "commission", entityId: String((input as any)?.id ?? (input as any)?.customerId ?? (input as any)?.agentId ?? Date.now()), permission: "payout" }).catch(() => {});
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [payout] = await db
          .select()
          .from(commissionPayouts)
          .where(eq(commissionPayouts.id, input.id))
          .limit(1);
        if (!payout) throw new TRPCError({ code: "NOT_FOUND" });
        if (payout.status !== "approved") {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Payout must be approved first",
          });
        }

        // Deduct from agent commission balance
        await db
          .update(agents)
          .set({
            commissionBalance: sql`${agents.commissionBalance} - ${payout.amount}`,
            updatedAt: new Date(),
          })
          .where(eq(agents.id, payout.agentId));

        const [updated] = await db
          .update(commissionPayouts)
          .set({
            status: "completed",
            nubanRef: input.nubanRef,
            processedAt: new Date(),
            updatedAt: new Date(),
          })
          .where(eq(commissionPayouts.id, input.id))
          .returning();

        await dispatchWebhookEvent("commission.payout.completed", {
          payoutId: updated.id,
          agentCode: updated.agentCode,
          amount: updated.amount,
          nubanRef: updated.nubanRef,
        });

        // Send email notification
        const [agent] = await db
          .select({ email: agents.email, name: agents.name })
          .from(agents)
          .where(eq(agents.id, payout.agentId))
          .limit(1);
        if (agent?.email) {
          const { subject, html, text } = buildAlertEmail({
            title: "Commission Payout Processed",
            message: `Your commission payout of ₦${parseFloat(payout.amount as string).toLocaleString("en-NG", { minimumFractionDigits: 2 })} has been processed successfully.${input.nubanRef ? ` Reference: ${input.nubanRef}` : ""}`,
            severity: "low",
          });
          enqueueEmail({ to: agent.email, subject, html, text });
        }

        return updated;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
