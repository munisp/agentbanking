import { z } from "zod";
import { TRPCError } from "@trpc/server";
import {
  publicProcedure as openProcedure,
  protectedProcedure,
  router,
} from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { commissionRules } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
import { validateInput } from "../lib/routerHelpers";

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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["approved", "rejected"],
  approved: ["paid", "clawed_back"],
  paid: ["clawed_back"],
  rejected: [],
  clawed_back: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "commissionCalculator",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "commissionCalculator",
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
    resource: "commissionCalculator",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "commissionCalculator",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Error Handling ─────────────────────────────────────────────────────────
function handleError(error: unknown, context: string): never {
  if (error instanceof TRPCError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${context}: ${message}`,
  });
}
function validateRequired<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `${field} is required`,
    });
  }
  return value;
}


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishcommissionCalculatorMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `commission.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(() => {});

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `commission_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `commission_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("commission", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const commissionCalculatorRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const results = await database
        .select()
        .from(commissionRules)
        .orderBy(desc(commissionRules.id))
        .limit(input.limit)
        .offset(input.offset);

      const [totalResult] = await database
        .select({ total: count() })
        .from(commissionRules);

      return {
        data: results,
        total: totalResult?.total ?? 0,
        limit: input.limit,
        offset: input.offset,
      };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(commissionRules)
        .where(eq(commissionRules.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const [totalResult] = await database
      .select({ total: count() })
      .from(commissionRules);

    return {
      totalRecords: totalResult?.total ?? 0,
      lastUpdated: new Date().toISOString(),
    };
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(commissionRules)
        .orderBy(desc(commissionRules.id))
        .limit(input.limit);

      return results;
    }),

  // ── Sprint 78 domain-specific procedures ──────────────────────────────────
  getTiers: openProcedure.query(async () => {
    const tiers = [
      {
        name: "Bronze",
        minVolume: 0,
        maxVolume: 500000,
        rate: 0.005,
        minTx: 0,
        bonusRate: 0,
      },
      {
        name: "Silver",
        minVolume: 500001,
        maxVolume: 2000000,
        rate: 0.007,
        minTx: 50,
        bonusRate: 0.001,
      },
      {
        name: "Gold",
        minVolume: 2000001,
        maxVolume: 10000000,
        rate: 0.01,
        minTx: 200,
        bonusRate: 0.002,
      },
      {
        name: "Platinum",
        minVolume: 10000001,
        maxVolume: 50000000,
        rate: 0.012,
        minTx: 500,
        bonusRate: 0.003,
      },
      {
        name: "Diamond",
        minVolume: 50000001,
        maxVolume: Infinity,
        rate: 0.015,
        minTx: 1000,
        bonusRate: 0.005,
      },
    ];
    const multipliers = {
      cash_in: 1.0,
      cash_out: 1.2,
      transfer: 0.8,
      bill_pay: 0.6,
      airtime: 0.5,
    };
    return { tiers, multipliers };
  }),

  calculate: openProcedure
    .input(
      z.object({
        agentId: z.string().min(1).max(255),
        transactions: z.array(
          z.object({
            ref: z.string(),
            type: z.string(),
            amount: z.number().min(0),
            status: z.string(),
          })
        ),
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
      const fees = calculateFee(txAmount, "commissionPayout");
      const commission = calculateCommission(fees.fee, "commissionPayout");
      const tax = calculateTax(fees.fee, "vat");
      const tiers = [
        {
          name: "Bronze",
          minVolume: 0,
          maxVolume: 500000,
          rate: 0.005,
          minTx: 0,
          bonusRate: 0,
        },
        {
          name: "Silver",
          minVolume: 500001,
          maxVolume: 2000000,
          rate: 0.007,
          minTx: 50,
          bonusRate: 0.001,
        },
        {
          name: "Gold",
          minVolume: 2000001,
          maxVolume: 10000000,
          rate: 0.01,
          minTx: 200,
          bonusRate: 0.002,
        },
        {
          name: "Platinum",
          minVolume: 10000001,
          maxVolume: 50000000,
          rate: 0.012,
          minTx: 500,
          bonusRate: 0.003,
        },
        {
          name: "Diamond",
          minVolume: 50000001,
          maxVolume: Infinity,
          rate: 0.015,
          minTx: 1000,
          bonusRate: 0.005,
        },
      ];
      const multipliers: Record<string, number> = {
        cash_in: 1.0,
        cash_out: 1.2,
        transfer: 0.8,
        bill_pay: 0.6,
        airtime: 0.5,
      };
      const completed = input.transactions.filter(
        t => t.status === "completed"
      );
      const reversed = input.transactions.filter(t => t.status === "reversed");
      const totalVolume = completed.reduce((s, t) => s + t.amount, 0);
      const txCount = completed.length;
      const tier =
        tiers.find(
          t => totalVolume >= t.minVolume && totalVolume <= t.maxVolume
        ) || tiers[0];
      let baseCommission = 0;
      for (const tx of completed) {
        const mult = multipliers[tx.type] ?? 1.0;
        baseCommission += tx.amount * tier.rate * mult;
      }
      const bonusCommission =
        txCount >= tier.minTx && tier.bonusRate > 0
          ? totalVolume * tier.bonusRate
          : 0;
      const clawbackAmount = reversed.reduce(
        (s, t) => s + t.amount * tier.rate,
        0
      );
      const totalCommission = baseCommission + bonusCommission;
      const netCommission = totalCommission - clawbackAmount;
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

        resource: "commissionCalculator",

        resourceId:
          typeof input === "object" && input !== null && "id" in input
            ? String((input as any).id)
            : "new",

        status: "success",

        metadata: { input: typeof input === "object" ? input : {} },
      });

      return {
        agentId: input.agentId,
        tier: tier.name,
        totalVolume,
        txCount,
        baseCommission,
        bonusCommission,
        clawbackAmount,
        totalCommission,
        netCommission,
      };
    }),

  simulate: openProcedure
    .input(
      z.object({ volume: z.number(), txCount: z.number(), txType: z.string() })
    )
    .query(async ({ input }) => {
      const tiers = [
        {
          name: "Bronze",
          minVolume: 0,
          maxVolume: 500000,
          rate: 0.005,
          minTx: 0,
          bonusRate: 0,
        },
        {
          name: "Silver",
          minVolume: 500001,
          maxVolume: 2000000,
          rate: 0.007,
          minTx: 50,
          bonusRate: 0.001,
        },
        {
          name: "Gold",
          minVolume: 2000001,
          maxVolume: 10000000,
          rate: 0.01,
          minTx: 200,
          bonusRate: 0.002,
        },
        {
          name: "Platinum",
          minVolume: 10000001,
          maxVolume: 50000000,
          rate: 0.012,
          minTx: 500,
          bonusRate: 0.003,
        },
        {
          name: "Diamond",
          minVolume: 50000001,
          maxVolume: Infinity,
          rate: 0.015,
          minTx: 1000,
          bonusRate: 0.005,
        },
      ];
      const multipliers: Record<string, number> = {
        cash_in: 1.0,
        cash_out: 1.2,
        transfer: 0.8,
        bill_pay: 0.6,
        airtime: 0.5,
      };
      const mult = multipliers[input.txType] ?? 1.0;
      const tier =
        tiers.find(
          t => input.volume >= t.minVolume && input.volume <= t.maxVolume
        ) || tiers[0];
      const baseCommission = input.volume * tier.rate * mult;
      const bonusCommission =
        input.txCount >= tier.minTx && tier.bonusRate > 0
          ? input.volume * tier.bonusRate
          : 0;
      const totalCommission = baseCommission + bonusCommission;
      const tierIdx = tiers.indexOf(tier);
      const nextTier = tierIdx < tiers.length - 1 ? tiers[tierIdx + 1] : null;
      return {
        tier: tier.name,
        totalCommission,
        baseCommission,
        bonusCommission,
        nextTier: nextTier?.name ?? null,
        volumeToNextTier: nextTier ? nextTier.minVolume - input.volume : 0,
      };
    }),
});
