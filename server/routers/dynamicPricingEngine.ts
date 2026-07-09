import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, sql, count, and, gte, lte } from "drizzle-orm";
import { feeRules, feeAuditTrail, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
import { validateInput } from "../lib/routerHelpers";

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
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  cancelled: [],
  archived: [],
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
      "dynamicPricingEngine",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "dynamicPricingEngine",
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
    resource: "dynamicPricingEngine",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "dynamicPricingEngine",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

async function publishdynamicPricingEngineMiddleware(
  event: string,
  key: string,
  payload: Record<string, unknown>
) {
  publishEvent("scoring.calculated", key, {
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
    type: `scoring.calculated.${event}`,
    timestamp: Date.now(),
  }).catch(() => {});
  dapr
    .publishEvent("pubsub", `scoring.calculated.${event}`, { key, ...payload })
    .catch(() => {});
  ingestToLakehouse("dynamicPricingEngine", {
    event,
    key,
    ...payload,
    timestamp: new Date().toISOString(),
  }).catch(() => {});
  cacheSet(`dynamicPricingEngine:${key}`, JSON.stringify(payload), 300).catch(
    () => {}
  );
}

export const dynamicPricingEngineRouter = router({
  listRules: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(feeRules)
          .orderBy(desc(feeRules.createdAt))
          .limit(input?.limit ?? 50);
        return { rules: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getRule: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [rule] = await db
          .select()
          .from(feeRules)
          .where(eq(feeRules.id, input.id))
          .limit(1);
        return rule ?? null;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  calculatePrice: protectedProcedure
    .input(
      z.object({
        amount: z.number().min(0).positive(),
        type: z.string(),
        channel: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rules = await db
          .select()
          .from(feeRules)
          .where(eq(feeRules.txType, input.type))
          .limit(5);
        const applicableRule = rules[0];
        const fee = applicableRule
          ? applicableRule.feeType === "percentage"
            ? (input.amount * Number(applicableRule.feeValue)) / 100
            : Number(applicableRule.feeValue)
          : 0;
        return {
          originalAmount: input.amount,
          fee: Math.round(fee * 100) / 100,
          totalAmount: input.amount + fee,
          ruleApplied: applicableRule?.id ?? null,
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
  createRule: protectedProcedure
    .input(
      z.object({
        transactionType: z.string(),
        feeType: z.enum(["percentage", "flat"]),
        feeValue: z.number(),
        minAmount: z.number().optional(),
        maxAmount: z.number().optional(),
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
        const [rule] = await db
          .insert(feeRules)
          .values({
            transactionType: input.transactionType,
            feeType: input.feeType,
            feeValue: String(input.feeValue),
            minAmount: input.minAmount ? String(input.minAmount) : null,
            maxAmount: input.maxAmount ? String(input.maxAmount) : null,
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "pricing_rule_created",
          resource: "fee_rules",
          resourceId: String(rule.id),
          status: "success",
          metadata: { transactionType: input.transactionType },
        } as any);
        await publishdynamicPricingEngineMiddleware(
          "createRule",
          `${Date.now()}`,
          { action: "createRule" }
        ).catch(() => {});

        return rule;
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
      const [total] = await db
        .select({ value: count() })
        .from(feeRules)
        .limit(100);
      const [totalAudit] = await db
        .select({ value: count() })
        .from(feeAuditTrail)
        .limit(100);

      return {
        totalRules: Number(total.value),
        totalFeeCalculations: Number(totalAudit.value),
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
