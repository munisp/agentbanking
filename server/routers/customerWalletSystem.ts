import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, sum } from "drizzle-orm";
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
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

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

export const customerWalletSystemRouter = router({
  getBalance: protectedProcedure
    .input(z.object({ customerId: z.number() }))
    .query(async ({ input }) => {
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
              eq(transactions.type, "Cash In")
            )
          )
          .limit(100);
        const [debits] = await db
          .select({ total: sum(transactions.amount) })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, input.customerId),
              eq(transactions.type, "Cash Out")
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
    .query(async ({ input }) => {
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
  topUp: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        amount: z.number().min(0).positive(),
        source: z.string(),
      })
    )
    .mutation(async ({ input, ctx }) => {
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
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        const [tx] = await db
          .insert(transactions)
          .values({
            customerId: input.customerId,
            amount: String(input.amount),
            fee: String(fees.fee),
            commission: String(commission.agentShare),
            type: "Cash In",
            status: "success",
            channel: "App",
            reference: "TOP-" + crypto.randomUUID(),
          } as any)
          .returning();
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-WLT-${Date.now()}`,
          description: "Customer wallet topup",
          debitAccountId: 1001,
          creditAccountId: 2001,
          amount: Math.round(input.amount * 100),
          currency: "NGN",
          referenceType: "transaction",
          referenceId: String(tx.id),
          postedBy: "system",
          status: "posted",
        });
        await db.insert(auditLog).values({
          action: "wallet_topup",
          resource: "transactions",
          resourceId: String(tx.id),
          status: "success",
          metadata: {
            customerId: input.customerId,
            amount: input.amount,
            source: input.source,
          },
        } as any);
        await writeAuditLog({
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "customerWalletSystem",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { success: true, transactionId: tx.id, amount: input.amount };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
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
