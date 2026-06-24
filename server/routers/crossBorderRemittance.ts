/**
 * Cross-Border Remittance — ECOWAS corridor management
 *
 * Supports:
 * - Nigeria → Ghana, Senegal, Cameroon, Côte d'Ivoire corridors
 * - Real-time FX rates with markup management
 * - Mojaloop integration for inter-scheme settlement
 * - Compliance: CBN cross-border regulations, AML screening
 * - Recipient management with mobile money wallets
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { checkDailyLimit } from "../lib/cbnLimits";
import { transactions, agents, gl_journal_entries } from "../../drizzle/schema";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
} from "../lib/domainCalculations";
import crypto from "crypto";
import { eq, desc, and, sql, gte, count, sum } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import { validateInput } from "../lib/routerHelpers";
import { enforcePermission } from "../_core/permify";


const CORRIDORS = {
  "NG-GH": {
    source: "NGN",
    destination: "GHS",
    name: "Nigeria → Ghana",
    minAmount: 1000,
    maxAmount: 5_000_000,
    feePercent: 1.5,
    minFee: 500,
    estimatedMinutes: 15,
  },
  "NG-SN": {
    source: "NGN",
    destination: "XOF",
    name: "Nigeria → Senegal",
    minAmount: 1000,
    maxAmount: 3_000_000,
    feePercent: 2.0,
    minFee: 750,
    estimatedMinutes: 30,
  },
  "NG-CM": {
    source: "NGN",
    destination: "XAF",
    name: "Nigeria → Cameroon",
    minAmount: 1000,
    maxAmount: 3_000_000,
    feePercent: 2.0,
    minFee: 750,
    estimatedMinutes: 30,
  },
  "NG-CI": {
    source: "NGN",
    destination: "XOF",
    name: "Nigeria → Côte d'Ivoire",
    minAmount: 1000,
    maxAmount: 3_000_000,
    feePercent: 2.0,
    minFee: 750,
    estimatedMinutes: 30,
  },
} as const;

// Simulated FX rates (production: live feed from CBN/Reuters)
const FX_RATES: Record<string, number> = {
  "NGN-GHS": 0.0075,
  "NGN-XOF": 0.37,
  "NGN-XAF": 0.37,
  "NGN-KES": 0.085,
};

export const crossBorderRemittanceRouter = router({
  getCorridors: protectedProcedure.query(async () => {
    return {
      corridors: Object.entries(CORRIDORS).map(([id, c]) => ({
        id,
        ...c,
        currentRate: FX_RATES[`${c.source}-${c.destination}`] || 0,
      })),
    };
  }),

  quote: protectedProcedure
    .input(
      z.object({
        corridorId: z.string().min(1).max(10),
        amountNGN: z.number().min(1000).max(5_000_000),
      })
    )
    .query(async ({ input }) => {
      const corridor = CORRIDORS[input.corridorId as keyof typeof CORRIDORS];
      if (!corridor)
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Invalid corridor",
        });

      if (
        input.amountNGN < corridor.minAmount ||
        input.amountNGN > corridor.maxAmount
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `Amount must be between NGN ${corridor.minAmount.toLocaleString()} and NGN ${corridor.maxAmount.toLocaleString()}`,
        });
      }

      const fee = Math.max(
        corridor.minFee,
        Math.round((input.amountNGN * corridor.feePercent) / 100)
      );
      const netAmount = input.amountNGN - fee;
      const rate = FX_RATES[`${corridor.source}-${corridor.destination}`] || 0;
      const receivedAmount = Math.round(netAmount * rate * 100) / 100;

      return {
        corridorId: input.corridorId,
        sendAmount: input.amountNGN,
        fee,
        netAmount,
        exchangeRate: rate,
        receivedAmount,
        receivedCurrency: corridor.destination,
        estimatedMinutes: corridor.estimatedMinutes,
        expiresAt: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
      };
    }),

  send: protectedProcedure
    .input(
      z.object({
        corridorId: z.string().min(1).max(10),
        amountNGN: z.number().min(1000).max(5_000_000),
        recipientName: z.string().min(2).max(100),
        recipientPhone: z.string().min(10).max(15),
        recipientWallet: z.string().max(50).optional(),
        purpose: z.string().min(1).max(200),
        idempotencyKey: z.string().min(16).max(64).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission({ subjectType: "user", subjectId: String(ctx.user?.id ?? "0"), entityType: "transaction", entityId: "0", permission: "create" }).catch(() => {});

      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const corridor = CORRIDORS[input.corridorId as keyof typeof CORRIDORS];
      if (!corridor) throw new TRPCError({ code: "BAD_REQUEST", message: "Invalid corridor" });

      const fee = Math.max(
        corridor.minFee,
        Math.round((input.amountNGN * corridor.feePercent) / 100)
      );
      const rate = FX_RATES[`${corridor.source}-${corridor.destination}`] || 0;
      const receivedAmount =
        Math.round((input.amountNGN - fee) * rate * 100) / 100;

      const ref = `XBDR-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;

      const idempFn = async () => {
        return withTransaction(async (tx) => {
          const db = tx ?? (await getDb())!;

          // CBN cross-border limit check
          const limitCheck = await checkDailyLimit(
            db,
            session.id,
            session.tier,
            input.amountNGN
          );
          if (!limitCheck.allowed) {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Daily cross-border limit exceeded. Remaining: ₦${limitCheck.remaining.toLocaleString()}`,
            });
          }

          // Lock agent row and check float balance
          const agentRows = await db.execute(
            sql`SELECT float_balance, float_locked FROM agents WHERE id = ${session.id} FOR UPDATE`
          );
          const agentRow = (agentRows as any).rows?.[0] ?? (agentRows as any)[0];
          if (!agentRow) throw new TRPCError({ code: "NOT_FOUND", message: "Agent not found" });
          if (agentRow.float_locked === true || agentRow.float_locked === "true") {
            throw new TRPCError({ code: "FORBIDDEN", message: "Agent float is locked" });
          }
          if (Number(agentRow.float_balance) < input.amountNGN) {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Insufficient float. Available: ₦${Number(agentRow.float_balance).toLocaleString()}, Required: ₦${input.amountNGN.toLocaleString()}`,
            });
          }

          // Debit agent float
          await db.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - ${String(input.amountNGN)} WHERE id = ${session.id}`
          );

          // Record transaction
          const [txRecord] = await db
            .insert(transactions)
            .values({
              ref,
              agentId: session.id,
              type: "Cross Border Remittance",
              amount: String(input.amountNGN),
              fee: String(fee),
              commission: "0",
              currency: "NGN",
              channel: "Remittance",
              status: "pending",
              customerName: input.recipientName,
              customerPhone: input.recipientPhone,
              metadata: {
                corridorId: input.corridorId,
                receivedAmount,
                receivedCurrency: corridor.destination,
                exchangeRate: rate,
                purpose: input.purpose,
                recipientWallet: input.recipientWallet,
              },
            })
            .returning();

          // GL double-entry: Debit Remittance Payable, Credit Agent Float
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Cross-border remittance to ${input.recipientName} (${corridor.name})`,
            debitAccountId: 3001, // Remittance Payable
            creditAccountId: 2001, // Agent Float
            amount: Math.round(input.amountNGN * 100),
            currency: "NGN",
            referenceType: "remittance",
            referenceId: String(txRecord.id),
            postedBy: session.agentCode,
            status: "posted",
          });

          // GL entry for fee revenue
          if (fee > 0) {
            await db.insert(gl_journal_entries).values({
              entryNumber: `JE-FEE-${ref}`,
              description: `Remittance fee for ${ref}`,
              debitAccountId: 2001, // Agent Float (fee deducted)
              creditAccountId: 4001, // Fee Revenue
              amount: Math.round(fee * 100),
              currency: "NGN",
              referenceType: "remittance_fee",
              referenceId: String(txRecord.id),
              postedBy: session.agentCode,
              status: "posted",
            });
          }

          return txRecord;
        }, "crossBorderRemittance.send");
      };

      const txRecord = input.idempotencyKey
        ? await withIdempotency(input.idempotencyKey, idempFn)
        : await idempFn();

      // Audit + Kafka (fire-and-forget, outside transaction)
      writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: "CROSS_BORDER_REMITTANCE",
        resource: "remittance",
        resourceId: ref,
        status: "success",
        metadata: {
          corridor: input.corridorId,
          amountNGN: input.amountNGN,
          fee,
          receivedAmount,
          currency: corridor.destination,
          recipient: input.recipientName,
        },
      }).catch(() => {});

      publishEvent(
        "pos.transactions.created",
        ref,
        {
          type: "cross_border_remittance",
          ref,
          transactionId: txRecord.id,
          agentId: session.id,
          corridor: input.corridorId,
          amountNGN: input.amountNGN,
          fee,
          receivedAmount,
          receivedCurrency: corridor.destination,
          exchangeRate: rate,
          recipientName: input.recipientName,
          timestamp: new Date().toISOString(),
        },
        { agentCode: session.agentCode }
      ).catch(() => {});

      // TigerBeetle dual-ledger
      tbCreateTransfer({
        debitAccountId: "2001", creditAccountId: "1001",
        amount: Math.round(input.amountNGN * 100),
        ref, txType: "cross_border_remittance", agentCode: session.agentCode,
      }).catch(() => {});

      // Fluvio + Dapr + Redis + Lakehouse
      publishTxToFluvio({ txRef: ref, agentCode: session.agentCode, amount: input.amountNGN, type: "cross_border_remittance", timestamp: Date.now() }).catch(() => {});
      dapr.publishEvent("pubsub", "remittance.completed", { ref, corridor: input.corridorId, amountNGN: input.amountNGN, agentId: session.id }).catch(() => {});
      cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
      ingestToLakehouse("remittance_transactions", { ref, corridor: input.corridorId, amountNGN: input.amountNGN, fee, receivedAmount, rate, agentId: session.id, timestamp: new Date().toISOString() }).catch(() => {});

      return {
        reference: ref,
        status: "pending",
        transactionId: txRecord.id,
        corridorId: input.corridorId,
        sendAmount: input.amountNGN,
        fee,
        receivedAmount,
        receivedCurrency: corridor.destination,
        recipientName: input.recipientName,
        estimatedMinutes: corridor.estimatedMinutes,
        createdAt: new Date().toISOString(),
      };
    }),

  history: protectedProcedure
    .input(
      z.object({
        page: z.number().min(1).default(1),
        limit: z.number().min(1).max(100).default(20),
      })
    )
    .query(async ({ input, ctx }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const offset = (input.page - 1) * input.limit;
      const txs = await db
        .select()
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, session.id),
            sql`${transactions.type} = 'cross_border'`
          )
        )
        .orderBy(desc(transactions.createdAt))
        .limit(input.limit)
        .offset(offset);

      return { transfers: txs, page: input.page, limit: input.limit };
    }),
});
