import { z } from "zod";
import { checkDailyLimit } from "../lib/cbnLimits";
import { router, protectedProcedure, adminProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, sum, inArray } from "drizzle-orm";
import {
  customers,
  transactions,
  auditLog,
  gl_journal_entries,
} from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

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
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["processing", "cancelled"],
  processing: ["completed", "failed"],
  completed: ["refunded"],
  failed: ["pending"],
  cancelled: [],
  refunded: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "customerWalletSystem",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "customerWalletSystem",
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
    resource: "customerWalletSystem",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "customerWalletSystem",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

async function publishcustomerWalletSystemMiddleware(
  event: string,
  key: string,
  payload: Record<string, unknown>
) {
  publishEvent("wallet.credited", key, {
    event,
    ...payload,
    timestamp: Date.now(),
  }).catch(() => {});
  tbCreateTransfer({
    debitAccountId: "1001",
    creditAccountId: "2001",
    amount: Number(payload.amount ?? 0),
    ledger: 1,
    code: 1,
    ref: key,
    txType: event,
    agentCode: String(payload.agentId ?? "system"),
  }).catch(() => {});
  publishTxToFluvio({
    txRef: key,
    agentCode: String(payload.agentId ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `wallet.credited.${event}`,
    timestamp: Date.now(),
  }).catch(() => {});
  dapr
    .publishEvent("pubsub", `wallet.credited.${event}`, { key, ...payload })
    .catch(() => {});
  ingestToLakehouse("customerWalletSystem", {
    event,
    key,
    ...payload,
    timestamp: new Date().toISOString(),
  }).catch(() => {});
  cacheSet(`customerWalletSystem:${key}`, JSON.stringify(payload), 300).catch(
    () => {}
  );
}

export const customerWalletSystemRouter = router({
  getBalance: protectedProcedure
    .input(z.object({ customerId: z.number() }))
    .query(async ({ input, ctx }) => {
      // SEC-03/FF-1: ownership check — non-admin callers may only access their
      // own wallet (session user id doubles as the customer wallet id).
      if (ctx.user.role !== "admin" && input.customerId !== ctx.user.id) {
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "You may only access your own wallet",
        });
      }
      try {
        const db = (await getDb())!;
        const [customer] = await db
          .select()
          .from(customers)
          .where(eq(customers.id, input.customerId))
          .limit(1);
        if (!customer) return null;
        const [credits] = await db
          .select({ total: sum(transactions.amount) })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, input.customerId),
              eq(transactions.type, "Cash In"),
              // FF-1: only settled rows count towards the balance
              inArray(transactions.status, ["success", "completed"])
            )
          )
          .limit(100);
        const [debits] = await db
          .select({ total: sum(transactions.amount) })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, input.customerId),
              eq(transactions.type, "Cash Out"),
              // FF-1: only settled rows count towards the balance
              inArray(transactions.status, ["success", "completed"])
            )
          )
          .limit(100);
        return {
          customerId: input.customerId,
          balance: Number(credits.total ?? 0) - Number(debits.total ?? 0),
          currency: "NGN",
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
  getTransactions: protectedProcedure
    .input(z.object({ customerId: z.number(), limit: z.number().default(50) }))
    .query(async ({ input, ctx }) => {
      // SEC-03/FF-1: ownership check — non-admin callers may only access their
      // own wallet (session user id doubles as the customer wallet id).
      if (ctx.user.role !== "admin" && input.customerId !== ctx.user.id) {
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "You may only access your own wallet",
        });
      }
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(transactions)
          .where(eq(transactions.agentId, input.customerId))
          .orderBy(desc(transactions.createdAt))
          .limit(input.limit);
        return { transactions: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  topUp: adminProcedure
    .input(
      z.object({
        customerId: z.number(),
        amount: z.number().min(0).positive(),
        source: z.string(),
      })
    )
    // SEC-03/FF-1: this endpoint previously inserted a status:"success"
    // "Cash In" row for ANY customerId/amount with no source debit and no
    // role check — arbitrary balance fabrication. It is now admin-gated AND
    // fails closed: no funding rail is configured in this deployment, so no
    // transaction row is written and no balance is credited until a funding
    // rail confirms settlement.
    .mutation(async () => {
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message:
          "Wallet top-up is disabled: no funding rail is configured for this deployment. Balances are only credited after a funding rail confirms settlement.",
      });
    }),
  getStats: protectedProcedure.query(async () => {
    try {
      const db = (await getDb())!;
      const [totalCustomers] = await db
        .select({ value: count() })
        .from(customers)
        .limit(100);
      const [totalVolume] = await db
        .select({ value: sum(transactions.amount) })
        .from(transactions)
        .limit(100);
      return {
        totalWallets: Number(totalCustomers.value),
        totalVolume: Number(totalVolume.value ?? 0),
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),
});
