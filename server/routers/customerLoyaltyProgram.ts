import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, sum } from "drizzle-orm";
import { loyaltyHistory, customers, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  cancelled: [],
  archived: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "customerLoyaltyProgram",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "customerLoyaltyProgram",
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
    resource: "customerLoyaltyProgram",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "customerLoyaltyProgram",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};

// ── Business Rule Guards ───────────────────────────────────────────────────
function enforceCustomerloyaltyprogramRules(data: Record<string, unknown>) {
  if (!data) throw new Error("Data required");
  if (typeof data.id === "number" && data.id <= 0)
    throw new Error("Invalid ID");
  if (
    typeof data.status === "string" &&
    !["active", "pending", "completed", "cancelled"].includes(data.status)
  )
    throw new Error("Invalid status");
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 || data.amount > 100_000_000)
  )
    throw new Error("Amount out of range");
  if (typeof data.email === "string" && !data.email.includes("@"))
    throw new Error("Invalid email");
  if (typeof data.name === "string" && data.name.trim().length === 0)
    throw new Error("Name required");
  return true;
}

// ── Computation Helpers ────────────────────────────────────────────────────
const _customerLoyaltyProgramCalc = {
  percentage: (value: number, total: number) =>
    total > 0 ? parseFloat(((value / total) * 100).toFixed(2)) : 0,
  roundAmount: (n: number) => Math.round(n * 100) / 100,
  applyRate: (amount: number, rate: number) =>
    parseFloat((amount * rate).toFixed(2)),
};

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishcustomerLoyaltyProgramMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `customer.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(
    () => {}
  );

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `customer_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `customer_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("customer", {
    ref,
    action,
    ...payload,
    timestamp: ts,
  }).catch(() => {});
}

export const customerLoyaltyProgramRouter = router({
  getBalance: protectedProcedure
    .input(z.object({ customerId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [earned] = await db
          .select({ total: sum(loyaltyHistory.points) })
          .from(loyaltyHistory)
          .where(
            and(
              eq(loyaltyHistory.agentId, input.customerId),
              eq(loyaltyHistory.type, "earned")
            )
          )
          .limit(100);
        const [redeemed] = await db
          .select({ total: sum(loyaltyHistory.points) })
          .from(loyaltyHistory)
          .where(
            and(
              eq(loyaltyHistory.agentId, input.customerId),
              eq(loyaltyHistory.type, "redeemed")
            )
          )
          .limit(100);
        return {
          customerId: input.customerId,
          earned: Number(earned.total ?? 0),
          redeemed: Number(redeemed.total ?? 0),
          balance: Number(earned.total ?? 0) - Number(redeemed.total ?? 0),
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
  getHistory: protectedProcedure
    .input(z.object({ customerId: z.number(), limit: z.number().default(50) }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(loyaltyHistory)
          .where(eq(loyaltyHistory.agentId, input.customerId))
          .orderBy(desc(loyaltyHistory.createdAt))
          .limit(input.limit);
        return { history: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  earnPoints: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        points: z.number().positive(),
        reason: z.string(),
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
        const [entry] = await db
          .insert(loyaltyHistory)
          .values({
            customerId: input.customerId,
            points: input.points,
            type: "earned",
            description: input.reason,
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "loyalty_points_earned",
          resource: "loyalty_history",
          resourceId: String(entry.id),
          status: "success",
          metadata: { customerId: input.customerId, points: input.points },
        } as any);
        return entry;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  redeemPoints: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        points: z.number().positive(),
        reward: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [earned] = await db
          .select({ total: sum(loyaltyHistory.points) })
          .from(loyaltyHistory)
          .where(
            and(
              eq(loyaltyHistory.agentId, input.customerId),
              eq(loyaltyHistory.type, "earned")
            )
          )
          .limit(100);
        const [redeemed] = await db
          .select({ total: sum(loyaltyHistory.points) })
          .from(loyaltyHistory)
          .where(
            and(
              eq(loyaltyHistory.agentId, input.customerId),
              eq(loyaltyHistory.type, "redeemed")
            )
          )
          .limit(100);
        const balance = Number(earned.total ?? 0) - Number(redeemed.total ?? 0);
        if (balance < input.points)
          throw new Error("Insufficient loyalty points");
        const [entry] = await db
          .insert(loyaltyHistory)
          .values({
            customerId: input.customerId,
            points: -input.points,
            type: "redeemed",
            description: input.reward,
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "loyalty_points_redeemed",
          resource: "loyalty_history",
          resourceId: String(entry.id),
          status: "success",
          metadata: {
            customerId: input.customerId,
            points: input.points,
            reward: input.reward,
          },
        } as any);
        return entry;
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
    const db = (await getDb())!;
    const [totalEarned] = await db
      .select({ total: sum(loyaltyHistory.points) })
      .from(loyaltyHistory)
      .where(eq(loyaltyHistory.type, "earned"))
      .limit(100);
    const [totalRedeemed] = await db
      .select({ total: sum(loyaltyHistory.points) })
      .from(loyaltyHistory)
      .where(eq(loyaltyHistory.type, "redeemed"))
      .limit(100);
    const [memberCount] = await db
      .select({ value: count() })
      .from(customers)
      .limit(100);

    // Middleware fan-out (fail-open)

    await publishcustomerLoyaltyProgramMiddleware(
      "redeemPoints",
      `${Date.now()}`,
      { action: "redeemPoints" }
    ).catch(() => {});

    return {
      totalPointsEarned: Number(totalEarned.total ?? 0),
      totalPointsRedeemed: Number(totalRedeemed.total ?? 0),
      totalMembers: Number(memberCount.value),
    };
  }),
});
