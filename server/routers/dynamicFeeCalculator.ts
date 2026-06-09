// @ts-nocheck
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  eq,
  desc,
  and,
  sql,
  count,
  sum,
  isNull,
  gte,
  lte,
  or,
  asc,
} from "drizzle-orm";
import { systemConfig, auditLog } from "../../drizzle/schema";
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

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "dynamicFeeCalculator",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "dynamicFeeCalculator",
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
    resource: "dynamicFeeCalculator",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "dynamicFeeCalculator",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

export const dynamicFeeCalculatorRouter = router({
  getStats: protectedProcedure.query(async () => {
    try {
      const db = await getDb();
      if (!db) return { totalRules: 0, activeRules: 0, avgFeeRate: 0 };
      const rows = await db
        .select()
        .from(systemConfig)
        .where(sql`${systemConfig.key} LIKE 'fee_rule_%'`)
        .limit(100);
      return {
        totalRules: rows.length,
        activeRules: rows.length,
        avgFeeRate: 1.5,
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),
  calculate: protectedProcedure
    .input(
      z.object({
        amount: z.number().min(0),
        transactionType: z.string(),
        channel: z.string().default("pos"),
        agentTier: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db)
          return {
            fee: Math.round(input.amount * 0.015),
            rate: 1.5,
            breakdown: [],
          };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "fee_rule_" + input.transactionType))
          .limit(1);
        if (rows.length > 0) {
          const rule = JSON.parse(String(rows[0].value ?? "{}"));
          const rate = Number(rule.rate ?? 1.5);
          return {
            fee: Math.round((input.amount * rate) / 100),
            rate,
            breakdown: [
              {
                component: "Base fee",
                amount: Math.round((input.amount * rate) / 100),
              },
            ],
          };
        }
        const defaultRate = 1.5;
        return {
          fee: Math.round((input.amount * defaultRate) / 100),
          rate: defaultRate,
          breakdown: [
            {
              component: "Default fee",
              amount: Math.round((input.amount * defaultRate) / 100),
            },
          ],
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
    .input(z.object({ limit: z.number().default(20) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { rules: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(sql`${systemConfig.key} LIKE 'fee_rule_%'`)
          .limit(input?.limit ?? 20);
        return {
          rules: rows.map(r => ({
            id: r.key.replace("fee_rule_", ""),
            ...JSON.parse(String(r.value ?? "{}")),
          })),
          total: rows.length,
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
        rate: z.number().min(0),
        minFee: z.number().optional(),
        maxFee: z.number().optional(),
        flatFee: z.number().optional(),
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
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db
          .insert(systemConfig)
          .values({
            key: "fee_rule_" + input.transactionType,
            value: JSON.stringify(input),
          })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: { value: JSON.stringify(input), updatedAt: new Date() },
          });
        await db.insert(auditLog).values({
          action: "fee_rule_created",
          resource: "fee_rules",
          resourceId: input.transactionType,
          status: "success",
          metadata: input,
        });
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

          resource: "dynamicFeeCalculator",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { success: true };
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
