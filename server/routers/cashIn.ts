import crypto from "crypto";
import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agents, transactions, gl_journal_entries } from "../../drizzle/schema";
import { eq, and, gte, sql, count, sum } from "drizzle-orm";
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
} from "../lib/domainCalculations";
import { checkDailyLimit, KYC_TIER_LIMITS } from "../lib/cbnLimits";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import { eventBus, EVENTS } from "../lib/eventBus";
import { enforcePermission } from "../_core/permify";


/**
 * Cash In Router — Agent accepts physical cash from customer and credits their account.
 *
 * Flow: Validate → Check limits → Calculate fees → Debit customer (conceptual) →
 *       Credit agent float → Record transaction → Double-entry journal → Audit → Receipt
 */
export const cashInRouter = router({
  /**
   * Process a cash deposit from a customer.
   * Enforces: CBN tier limits, idempotency, double-entry, audit trail.
   */
  deposit: protectedProcedure
    .input(
      z.object({
        amount: z.number().positive().min(100).max(10_000_000),
        customerPhone: z.string().min(11).max(15),
        customerName: z.string().min(2).max(128),
        customerAccount: z.string().min(10).max(20).optional(),
        narration: z.string().max(256).optional(),
        idempotencyKey: z.string().min(16).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission(String(ctx.user?.id ?? "0"), "transaction", "create").catch(() => {});

      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        // Validate amount
        const amountCheck = validateAmount(input.amount, {
          min: 100,
          max: 10_000_000,
        });
        if (!amountCheck.valid)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: amountCheck.error!,
          });

        // Calculate fees
        const feeResult = calculateFee(input.amount, "cashIn");
        const commResult = calculateCommission(feeResult.fee, "cashIn");
        const taxResult = calculateTax(feeResult.fee, "vat");

        const netAmount = input.amount - feeResult.fee;
        const ref = `CI-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;

        return withTransaction(async tx => {
          const db = tx ?? (await getDb())!;

          // Check CBN daily cumulative limit
          const limitCheck = await checkDailyLimit(
            db,
            session.id,
            session.tier,
            input.amount
          );
          if (!limitCheck.allowed)
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Daily limit exceeded. Today: ₦${limitCheck.todayTotal.toLocaleString()}, Limit: ₦${limitCheck.dailyLimit.toLocaleString()}, Remaining: ₦${limitCheck.remaining.toLocaleString()}`,
            });

          // Lock agent row to prevent concurrent balance race conditions
          const agentRows = await db.execute(
            sql`SELECT float_balance, float_limit, float_locked FROM agents WHERE id = ${session.id} FOR UPDATE`
          );
          const agentRow = (agentRows as any).rows?.[0] ?? (agentRows as any)[0];
          const agent = agentRow ? {
            floatBalance: agentRow.float_balance,
            floatLimit: agentRow.float_limit,
            floatLocked: agentRow.float_locked,
          } : null;

          if (!agent)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "Agent not found",
            });
          if (agent.floatLocked === true || agent.floatLocked === "true")
            throw new TRPCError({
              code: "FORBIDDEN",
              message: "Agent float is locked",
            });

          const newBalance = Number(agent.floatBalance) + netAmount;
          if (newBalance > Number(agent.floatLimit))
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Float limit exceeded. Current: ₦${Number(agent.floatBalance).toLocaleString()}, Limit: ₦${Number(agent.floatLimit).toLocaleString()}`,
            });

          // All writes use the same transaction (tx from outer withTransaction)
          // Credit agent float balance
          await db
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) + ${String(netAmount)}`,
            })
            .where(eq(agents.id, session.id));

          // Record transaction
          const [txRecord] = await db
            .insert(transactions)
            .values({
              ref,
              idempotencyKey: input.idempotencyKey,
              agentId: session.id,
              type: "Cash In",
              amount: String(input.amount),
              fee: String(feeResult.fee),
              commission: String(commResult.agentShare),
              currency: "NGN",
              customerName: input.customerName,
              customerPhone: input.customerPhone,
              customerAccount: input.customerAccount ?? null,
              channel: "Cash",
              status: "success",
              metadata: {
                narration: input.narration,
                feeBreakdown: feeResult.breakdown,
              },
            })
            .returning();

          // Double-entry journal: Debit Cash-on-Hand, Credit Agent Float
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Cash In deposit from ${input.customerName}`,
            debitAccountId: 1001, // Cash on Hand (asset)
            creditAccountId: 2001, // Agent Float Liability
            amount: Math.round(netAmount * 100), // Store in kobo
            currency: "NGN",
            referenceType: "transaction",
            referenceId: String(txRecord.id),
            postedBy: session.agentCode,
            status: "posted",
          });

          // Credit agent commission
          await db
            .update(agents)
            .set({
              commissionBalance: sql`CAST(${agents.commissionBalance} AS numeric) + ${String(commResult.agentShare)}`,
            })
            .where(eq(agents.id, session.id));

          // Audit trail (fire-and-forget, outside transaction)
          writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "CASH_IN",
            resource: "transaction",
            resourceId: ref,
            status: "success",
            metadata: {
              amount: input.amount,
              fee: feeResult.fee,
              commission: commResult.agentShare,
              tax: taxResult.taxAmount,
              netAmount,
              customerPhone: input.customerPhone,
            },
          }).catch(() => {});

          // Publish Kafka event for downstream consumers
          publishEvent(
            "pos.transactions.created",
            ref,
            {
              type: "cash_in",
              ref,
              transactionId: txRecord.id,
              agentId: session.id,
              amount: input.amount,
              fee: feeResult.fee,
              commission: commResult.agentShare,
              netAmount,
              currency: "NGN",
              customerPhone: input.customerPhone,
              customerName: input.customerName,
              timestamp: new Date().toISOString(),
            },
            { agentCode: session.agentCode }
          ).catch(() => {});

          // Emit internal event for real-time processing
          eventBus.emit(EVENTS.TRANSACTION_COMPLETED, {
            type: "cash_in",
            ref,
            amount: input.amount,
            agentId: session.id,
          });
          // TigerBeetle dual-ledger
          tbCreateTransfer({
            debitAccountId: "1001", creditAccountId: "2001",
            amount: Math.round(input.amount * 100),
            ref, txType: "cash_in", agentCode: session.agentCode,
          }).catch(() => {});
          // Fluvio + Dapr + Redis + Lakehouse
          publishTxToFluvio({ txRef: ref, agentCode: session.agentCode, amount: input.amount, type: "cash_in", timestamp: Date.now() }).catch(() => {});
          dapr.publishEvent("pubsub", "cash.in.completed", { ref, amount: input.amount, agentId: session.id, customerPhone: input.customerPhone }).catch(() => {});
          cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
          ingestToLakehouse("cash_in_transactions", { ref, amount: input.amount, fee: feeResult.fee, agentId: session.id, customerPhone: input.customerPhone, timestamp: new Date().toISOString() }).catch(() => {});

          return {
            success: true,
            ref,
            transactionId: txRecord.id,
            amount: input.amount,
            fee: feeResult.fee,
            feeBreakdown: feeResult.breakdown,
            commission: commResult.agentShare,
            tax: taxResult.taxAmount,
            netAmount,
            newFloatBalance: newBalance,
            customerName: input.customerName,
            customerPhone: input.customerPhone,
            timestamp: new Date().toISOString(),
            receiptData: {
              ref,
              type: "Cash In",
              amount: `₦${input.amount.toLocaleString()}`,
              fee: `₦${feeResult.fee.toLocaleString()}`,
              net: `₦${netAmount.toLocaleString()}`,
              agent: session.agentCode,
              customer: input.customerName,
              date: new Date().toISOString(),
            },
          };
        }, "cashIn.deposit");
      });
    }),

  /** Get today's deposit summary for the logged-in agent */
  todaySummary: protectedProcedure.query(async ({ ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session)
      throw new TRPCError({
        code: "UNAUTHORIZED",
        message: "Agent session required",
      });

    const db = (await getDb())!;
    if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const [stats] = await db
      .select({
        count: count(),
        totalAmount: sql<string>`COALESCE(SUM(CAST(amount AS numeric)), 0)`,
        totalFees: sql<string>`COALESCE(SUM(CAST(fee AS numeric)), 0)`,
        totalCommission: sql<string>`COALESCE(SUM(CAST(commission AS numeric)), 0)`,
      })
      .from(transactions)
      .where(
        and(
          eq(transactions.agentId, session.id),
          eq(transactions.type, "Cash In"),
          gte(transactions.createdAt, today)
        )
      );

    const tierLimit =
      KYC_TIER_LIMITS[session.tier as keyof typeof KYC_TIER_LIMITS] ??
      KYC_TIER_LIMITS.Bronze;

    return {
      depositsToday: stats?.count ?? 0,
      totalAmount: Number(stats?.totalAmount ?? 0),
      totalFees: Number(stats?.totalFees ?? 0),
      totalCommission: Number(stats?.totalCommission ?? 0),
      dailyLimit: tierLimit.daily,
      remaining: Math.max(0, tierLimit.daily - Number(stats?.totalAmount ?? 0)),
      tier: session.tier,
    };
  }),
});
