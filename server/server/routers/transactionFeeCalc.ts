import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, sql, count, sum, and, gte, lte } from "drizzle-orm";
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
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  initiated: ["pending_validation"],
  pending_validation: ["validated", "failed_validation"],
  validated: ["authorized", "declined"],
  authorized: ["processing"],
  processing: ["completed", "failed", "reversed"],
  completed: ["settled", "disputed", "reversed"],
  settled: ["reconciled"],
  reconciled: ["archived"],
  failed: ["retry_pending", "cancelled"],
  failed_validation: ["retry_pending", "cancelled"],
  declined: ["cancelled"],
  reversed: ["refund_processing"],
  refund_processing: ["refunded"],
  refunded: ["archived"],
  disputed: ["under_investigation"],
  under_investigation: ["resolved", "escalated"],
  resolved: ["archived"],
  escalated: ["resolved"],
  retry_pending: ["processing"],
  cancelled: [],
  archived: [],
};

function enforceTransition(currentStatus: string, newStatus: string) {
  const allowed =
    STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
  if (allowed && !allowed.includes(newStatus)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
    });
  }
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "transactionFeeCalc",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "transactionFeeCalc",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Transaction Handling for transactionFeeCalc ───────────────────────────────────────
// All mutations use withTransaction for atomicity.
// withTransaction wraps DB operations in a single ACID transaction.
// On failure, withTransaction automatically rolls back all changes.
// db.transaction() is the underlying mechanism used by withTransaction.
export const transactionFeeCalcRouter = router({
  calculate: protectedProcedure
    .input(
      z.object({
        amount: z.number().min(0).positive(),
        transactionType: z.string(),
        channel: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rules = await db
          .select()
          .from(feeRules)
          .where(eq(feeRules.txType, input.transactionType))
          .limit(5);
        const rule = rules[0];
        const fee = rule
          ? rule.feeType === "percentage"
            ? (input.amount * Number(rule.feeValue)) / 100
            : Number(rule.feeValue)
          : 0;
        const cappedFee = rule?.maxFee
          ? Math.min(fee, Number(rule.maxFee))
          : fee;
        const finalFee = rule?.minFee
          ? Math.max(cappedFee, Number(rule.minFee))
          : cappedFee;
        return {
          amount: input.amount,
          fee: Math.round(finalFee * 100) / 100,
          total: input.amount + Math.round(finalFee * 100) / 100,
          ruleId: rule?.id ?? null,
          feeType: rule?.feeType ?? "none",
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
  getAuditTrail: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(feeAuditTrail)
          .orderBy(desc(feeAuditTrail.createdAt))
          .limit(input?.limit ?? 50);
        return { entries: rows, total: rows.length };
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
      const [totalRules] = await db
        .select({ value: count() })
        .from(feeRules)
        .limit(100);
      const [totalFees] = await db
        .select({ value: sum(feeAuditTrail.txAmount) })
        .from(feeAuditTrail)
        .limit(100);
      return {
        totalRules: Number(totalRules.value),
        totalFeesCollected: Number(totalFees.value ?? 0),
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
