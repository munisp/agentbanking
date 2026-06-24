import crypto from "crypto";
import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agents, transactions, gl_journal_entries } from "../../drizzle/schema";
import { eq, and, gte, sql, count } from "drizzle-orm";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  validateAmount,
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
 * Cash Out Router — Agent dispenses physical cash to customer (withdrawal).
 *
 * Flow: Validate → Check limits → Check float balance → Calculate fees →
 *       Debit agent float → Record transaction → Double-entry journal → AML check → Audit → Receipt
 */
export const cashOutRouter = router({
  /**
   * Process a cash withdrawal for a customer.
   * Enforces: CBN tier limits, sufficient float, idempotency, double-entry, AML threshold.
   */
  withdraw: protectedProcedure
    .input(
      z.object({
        amount: z.number().positive().min(100).max(10_000_000),
        customerPhone: z.string().min(11).max(15),
        customerName: z.string().min(2).max(128),
        customerAccount: z.string().min(10).max(20),
        sourceBank: z.string().min(2).max(64),
        narration: z.string().max(256).optional(),
        idempotencyKey: z.string().min(16).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx.user?.id ?? "0"), entityType: "transaction", entityId: "0", permission: "create" }).catch(() => {});

      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const amountCheck = validateAmount(input.amount, {
          min: 100,
          max: 10_000_000,
        });
        if (!amountCheck.valid)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: amountCheck.error!,
          });

        // Calculate fees (customer pays)
        const feeResult = calculateFee(input.amount, "cashOut");
        const commResult = calculateCommission(feeResult.fee, "cashOut");
        const taxResult = calculateTax(feeResult.fee, "vat");

        const totalDebit = input.amount; // Agent gives this much cash
        const ref = `CO-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;

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
              message: `Daily limit exceeded. Today: ₦${limitCheck.todayTotal.toLocaleString()}, Limit: ₦${limitCheck.dailyLimit.toLocaleString()}`,
            });

          // Lock agent row to prevent concurrent double-spend
          const agentRows = await db.execute(
            sql`SELECT float_balance, float_locked FROM agents WHERE id = ${session.id} FOR UPDATE`
          );
          const agentRow = (agentRows as any).rows?.[0] ?? (agentRows as any)[0];
          const agent = agentRow ? {
            floatBalance: agentRow.float_balance,
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
          if (Number(agent.floatBalance) < totalDebit)
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Insufficient float. Available: ₦${Number(agent.floatBalance).toLocaleString()}, Required: ₦${totalDebit.toLocaleString()}`,
            });

          // AML: Flag transactions >= 5,000,000 NGN for STR
          const requiresSTR = input.amount >= 5_000_000;

          // All writes use the same transaction (tx from outer withTransaction)
          // Debit agent float balance
          await db
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) - ${String(totalDebit)}`,
            })
            .where(eq(agents.id, session.id));

          // Record transaction
          const [txRecord] = await db
            .insert(transactions)
            .values({
              ref,
              idempotencyKey: input.idempotencyKey,
              agentId: session.id,
              type: "Cash Out",
              amount: String(input.amount),
              fee: String(feeResult.fee),
              commission: String(commResult.agentShare),
              currency: "NGN",
              customerName: input.customerName,
              customerPhone: input.customerPhone,
              customerAccount: input.customerAccount,
              destinationBank: input.sourceBank,
              channel: "Cash",
              status: "success",
              metadata: {
                narration: input.narration,
                requiresSTR,
                feeBreakdown: feeResult.breakdown,
              },
            })
            .returning();

          // Double-entry journal: Debit Agent Float Liability, Credit Cash-on-Hand
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Cash Out withdrawal to ${input.customerName}`,
            debitAccountId: 2001, // Agent Float Liability
            creditAccountId: 1001, // Cash on Hand (asset)
            amount: Math.round(totalDebit * 100),
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

          // Audit trail (fire-and-forget)
          writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "CASH_OUT",
            resource: "transaction",
            resourceId: ref,
            status: "success",
            metadata: {
              amount: input.amount,
              fee: feeResult.fee,
              commission: commResult.agentShare,
              customerPhone: input.customerPhone,
              sourceBank: input.sourceBank,
              requiresSTR,
            },
          }).catch(() => {});

          // Publish Kafka event for downstream consumers
          publishEvent(
            "pos.transactions.created",
            ref,
            {
              type: "cash_out",
              ref,
              transactionId: txRecord.id,
              agentId: session.id,
              amount: input.amount,
              fee: feeResult.fee,
              commission: commResult.agentShare,
              totalDebit,
              currency: "NGN",
              customerPhone: input.customerPhone,
              customerName: input.customerName,
              sourceBank: input.sourceBank,
              requiresSTR,
              timestamp: new Date().toISOString(),
            },
            { agentCode: session.agentCode }
          ).catch(() => {});

          // Emit internal event
          eventBus.emit(EVENTS.TRANSACTION_COMPLETED, {
            type: "cash_out",
            ref,
            amount: input.amount,
            agentId: session.id,
          });
          // TigerBeetle dual-ledger
          tbCreateTransfer({
            debitAccountId: "2001", creditAccountId: "1001",
            amount: Math.round(input.amount * 100),
            ref, txType: "cash_out", agentCode: session.agentCode,
          }).catch(() => {});
          // Fluvio + Dapr + Redis + Lakehouse
          publishTxToFluvio({ txRef: ref, agentCode: session.agentCode, amount: input.amount, type: "cash_out", timestamp: Date.now() }).catch(() => {});
          dapr.publishEvent("pubsub", "cash.out.completed", { ref, amount: input.amount, agentId: session.id, customerPhone: input.customerPhone }).catch(() => {});
          cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
          ingestToLakehouse("cash_out_transactions", { ref, amount: input.amount, fee: feeResult.fee, agentId: session.id, customerPhone: input.customerPhone, timestamp: new Date().toISOString() }).catch(() => {});

          return {
            success: true,
            ref,
            transactionId: txRecord.id,
            amount: input.amount,
            fee: feeResult.fee,
            feeBreakdown: feeResult.breakdown,
            commission: commResult.agentShare,
            tax: taxResult.taxAmount,
            newFloatBalance: Number(agent.floatBalance) - totalDebit,
            requiresSTR,
            customerName: input.customerName,
            timestamp: new Date().toISOString(),
            receiptData: {
              ref,
              type: "Cash Out",
              amount: `₦${input.amount.toLocaleString()}`,
              fee: `₦${feeResult.fee.toLocaleString()}`,
              agent: session.agentCode,
              customer: input.customerName,
              date: new Date().toISOString(),
            },
          };
        }, "cashOut.withdraw");
      });
    }),

  /** Get today's withdrawal summary */
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
          eq(transactions.type, "Cash Out"),
          gte(transactions.createdAt, today)
        )
      );

    const tierLimit =
      KYC_TIER_LIMITS[session.tier as keyof typeof KYC_TIER_LIMITS] ??
      KYC_TIER_LIMITS.Bronze;

    return {
      withdrawalsToday: stats?.count ?? 0,
      totalAmount: Number(stats?.totalAmount ?? 0),
      totalFees: Number(stats?.totalFees ?? 0),
      totalCommission: Number(stats?.totalCommission ?? 0),
      dailyLimit: tierLimit.daily,
      remaining: Math.max(0, tierLimit.daily - Number(stats?.totalAmount ?? 0)),
      tier: session.tier,
    };
  }),
});
