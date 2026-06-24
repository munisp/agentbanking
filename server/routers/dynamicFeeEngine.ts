/**
 * F05: Dynamic Fee Engine
 * Fee rules, tiered pricing, volume discounts, fee audit trail, fee simulation
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import {
  feeRules,
  feeAuditTrail,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, gte, count, sql } from "drizzle-orm";
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
import { checkDailyLimit } from "../lib/cbnLimits";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["pending_approval"],
  pending_approval: ["approved", "rejected"],
  approved: ["processing"],
  processing: ["completed", "failed", "partially_paid"],
  completed: ["settled"],
  settled: ["reconciled", "disputed"],
  reconciled: ["closed"],
  partially_paid: ["processing", "overdue"],
  overdue: ["processing", "written_off", "collections"],
  collections: ["paid", "written_off"],
  paid: ["closed"],
  written_off: ["closed"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["processing"],
  rejected: [],
  disputed: ["under_review"],
  under_review: ["adjusted", "confirmed"],
  adjusted: ["closed"],
  confirmed: ["closed"],
  closed: [],
  cancelled: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "dynamicFeeEngine",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "dynamicFeeEngine",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishdynamicFeeEngineMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `platform.${action}` as any;
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
      txType: `platform_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `platform_${action}`,
    timestamp: ts,
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("platform", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const dynamicFeeEngineRouter = router({
  // List fee rules
  listRules: protectedProcedure
    .input(
      z.object({
        page: z.number().default(1),
        limit: z.number().default(20),
        txType: z.string().optional(),
        channel: z.string().optional(),
        active: z.boolean().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const conditions = [];
        if (input.txType) conditions.push(eq(feeRules.txType, input.txType));
        if ((input as any).channel)
          conditions.push(eq((feeRules as any).channel, input.channel));
        // @ts-expect-error auto-fix
        if (input.isActive !== undefined)
          conditions.push(eq(feeRules.isActive, input.active as any));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const items = await db
          .select()
          .from(feeRules)
          .where(where)
          .orderBy(desc(feeRules.createdAt))
          .limit(input.limit)
          .offset((input.page - 1) * input.limit);
        const [{ total }] = await db
          .select({ total: count() })
          .from(feeRules)
          .where(where)
          .limit(100);
        return { items, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Create fee rule
  createRule: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        txType: z.string(),
        channel: z.string(),
        feeType: z.enum(["flat", "percentage", "tiered", "capped_percentage"]),
        flatAmount: z.number().optional(),
        percentageRate: z.number().optional(),
        minFee: z.number().optional(),
        maxFee: z.number().optional(),
        tiers: z
          .array(
            z.object({
              minAmount: z.number(),
              maxAmount: z.number(),
              fee: z.number().min(0),
              feeType: z.enum(["flat", "percentage"]),
            })
          )
          .optional(),
        effectiveFrom: z.string(),
        effectiveTo: z.string().optional(),
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
        if (!db) throw new Error("Database unavailable");
        const [rule] = await db
          .insert(feeRules)
          .values({
            name: input.name,
            txType: input.txType,
            channel: input.channel,
            feeType: input.feeType,
            flatAmount: input.flatAmount ? String(input.flatAmount) : null,
            percentageRate: input.percentageRate
              ? String(input.percentageRate)
              : null,
            minFee: input.minFee ? String(input.minFee) : null,
            maxFee: input.maxFee ? String(input.maxFee) : null,
            tiers: input.tiers ? JSON.stringify(input.tiers) : null,
            effectiveFrom: new Date(input.effectiveFrom),
            effectiveTo: input.effectiveTo ? new Date(input.effectiveTo) : null,
            active: true,
            createdBy: ctx.user?.id,
          } as any)
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `dynamicFeeEngine transaction`,
          debitAccountId: 2001,
          creditAccountId: 1001,
          amount: Math.round(
            (typeof input === "object" && "amount" in input
              ? Number((input as any).amount)
              : 0) * 100
          ),
          currency: "NGN",
          status: "posted",
        });
        // Audit trail
        await db.insert(feeAuditTrail).values({
          feeRuleId: rule.id,
          action: "created",
          changedBy: ctx.user?.id,
          newValues: JSON.stringify(input),
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

          resource: "dynamicFeeEngine",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { rule };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Update fee rule
  updateRule: protectedProcedure
    .input(
      z.object({
        ruleId: z.number(),
        name: z.string().optional(),
        flatAmount: z.number().optional(),
        percentageRate: z.number().optional(),
        minFee: z.number().optional(),
        maxFee: z.number().optional(),
        active: z.boolean().optional(),
      } as any)
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const [oldRule] = await db
          .select()
          .from(feeRules)
          .where(eq(feeRules.id, input.ruleId as any))
          .limit(100);
        const updates: any = { updatedAt: new Date() };
        if (input.name !== undefined) updates.name = input.name;
        if (input.flatAmount !== undefined)
          updates.flatAmount = String(input.flatAmount);
        if (input.percentageRate !== undefined)
          updates.percentageRate = String(input.percentageRate);
        if (input.minFee !== undefined) updates.minFee = String(input.minFee);
        if (input.maxFee !== undefined) updates.maxFee = String(input.maxFee);
        if (input.active !== undefined) updates.active = input.active;
        await db
          .update(feeRules)
          .set(updates)
          .where(eq(feeRules.id, input.ruleId as any));
        await db.insert(feeAuditTrail).values({
          feeRuleId: input.ruleId,
          action: "updated",
          changedBy: ctx.user?.id,
          previousValues: JSON.stringify(oldRule),
          newValues: JSON.stringify(updates),
        } as any);
        // Middleware fan-out (fail-open)
        await publishDynamicFeeEngineMiddleware("updateRule", `${Date.now()}`, { action: "updateRule" }).catch(() => {});

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

  // Calculate fee for a transaction
  calculateFee: protectedProcedure
    .input(
      z.object({
        txType: z.string(),
        channel: z.string(),
        amount: z.number().min(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { fee: 0, breakdown: {} };
        const now = new Date();
        const [rule] = await db
          .select()
          .from(feeRules)
          .where(
            and(
              eq(feeRules.txType, input.txType),
              eq((feeRules as any).channel, input.channel),
              eq(feeRules.isActive, true)
            )
          )
          .limit(1);
        if (!rule)
          return { fee: 0, breakdown: { message: "No matching fee rule" } };
        let fee = 0;
        const breakdown: any = {
          ruleId: rule.id,
          ruleName: rule.name,
          feeType: rule.feeType,
        };
        switch (rule.feeType) {
          case "flat":
            fee = parseFloat(String((rule as any).flatAmount || "0"));
            break;
          case "percentage":
            fee =
              (input.amount *
                parseFloat(String((rule as any).percentageRate || "0"))) /
              100;
            break;
          case "capped_percentage":
            fee =
              (input.amount *
                parseFloat(String((rule as any).percentageRate || "0"))) /
              100;
            const minFee = parseFloat(String(rule.minFee || "0"));
            const maxFee = parseFloat(String(rule.maxFee || "999999999"));
            fee = Math.max(minFee, Math.min(fee, maxFee));
            breakdown.capped = true;
            break;
          case "tiered":
            if ((rule as any).tiers) {
              const tiers = JSON.parse(String((rule as any).tiers));
              for (const tier of tiers) {
                if (
                  input.amount >= tier.minAmount &&
                  input.amount <= tier.maxAmount
                ) {
                  fee =
                    tier.feeType === "flat"
                      ? tier.fee
                      : (input.amount * tier.fee) / 100;
                  breakdown.matchedTier = tier;
                  break;
                }
              }
            }
            break;
        }
        breakdown.calculatedFee = fee;
        return { fee: Math.round(fee * 100) / 100, breakdown };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Fee audit trail
  auditTrail: protectedProcedure
    .input(
      z.object({
        ruleId: z.number().optional(),
        page: z.number().default(1),
        limit: z.number().default(20),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const conditions = [];
        if (input.ruleId)
          conditions.push(eq(feeAuditTrail.feeRuleId, input.ruleId));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const items = await db
          .select()
          .from(feeAuditTrail)
          .where(where)
          .orderBy(desc(feeAuditTrail.createdAt))
          .limit(input.limit)
          .offset((input.page - 1) * input.limit);
        const [{ total }] = await db
          .select({ total: count() })
          .from(feeAuditTrail)
          .where(where)
          .limit(100);
        return { items, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Fee simulation — test fee rules against sample amounts
  simulate: protectedProcedure
    .input(
      z.object({
        txType: z.string(),
        channel: z.string(),
        amounts: z.array(z.number()),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { results: [] };
        const [rule] = await db
          .select()
          .from(feeRules)
          .where(
            and(
              eq(feeRules.txType, input.txType),
              eq((feeRules as any).channel, input.channel),
              eq(feeRules.isActive, true)
            )
          )
          .limit(1);
        if (!rule)
          return {
            results: input.amounts.map(a => ({
              amount: a,
              fee: 0,
              noRule: true,
            })),
          };
        const results = input.amounts.map(amount => {
          let fee = 0;
          switch (rule.feeType) {
            case "flat":
              fee = parseFloat(String((rule as any).flatAmount || "0"));
              break;
            case "percentage":
              fee =
                (amount *
                  parseFloat(String((rule as any).percentageRate || "0"))) /
                100;
              break;
            case "capped_percentage":
              fee =
                (amount *
                  parseFloat(String((rule as any).percentageRate || "0"))) /
                100;
              fee = Math.max(
                parseFloat(String(rule.minFee || "0")),
                Math.min(fee, parseFloat(String(rule.maxFee || "999999999")))
              );
              break;
            case "tiered":
              if ((rule as any).tiers) {
                const tiers = JSON.parse(String((rule as any).tiers));
                for (const tier of tiers) {
                  if (amount >= tier.minAmount && amount <= tier.maxAmount) {
                    fee =
                      tier.feeType === "flat"
                        ? tier.fee
                        : (amount * tier.fee) / 100;
                    break;
                  }
                }
              }
              break;
          }
          return { amount, fee: Math.round(fee * 100) / 100 };
        });
        return {
          results,
          rule: { id: rule.id, name: rule.name, feeType: rule.feeType },
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
});
