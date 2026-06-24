// Sprint 87: Event sequencing, funnel analysis, attribution
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { customerJourneySteps } from "../../drizzle/schema";
import { eq, desc, and, count, sql, gte, lte } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
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

const JOURNEY_STAGES = [
  "awareness",
  "consideration",
  "onboarding",
  "first_transaction",
  "active",
  "loyal",
  "churned",
];

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "customerJourneyEventsCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "customerJourneyEventsCrud",
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
    resource: "customerJourneyEventsCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "customerJourneyEventsCrud",
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


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishcustomerJourneyEventsCrudMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `customer.${action}` as any;
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
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("customer", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const customer_journey_eventsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        customerId: z.number().optional(),
        stage: z.string().optional(),
        limit: z.number().default(50),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.customerId)
          conditions.push(
            eq(customerJourneySteps.customerId, input.customerId)
          );
        if (input.stage)
          conditions.push(eq(customerJourneySteps.status, input.stage));
        const rows = await db
          .select()
          .from(customerJourneySteps)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(customerJourneySteps.id))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(customerJourneySteps)
          .where(conditions.length ? and(...conditions) : undefined)
          .limit(100);
        return { items: rows, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .select()
          .from(customerJourneySteps)
          .where(eq(customerJourneySteps.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Journey event not found",
          });
        return row;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  trackEvent: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        stage: z.enum([
          "awareness",
          "consideration",
          "onboarding",
          "first_transaction",
          "active",
          "loyal",
          "churned",
        ]),
        eventType: z.string(),
        metadata: z.record(z.string(), z.any()).optional(),
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
        const [row] = await db
          .insert(customerJourneySteps)
          .values({ ...input, createdAt: new Date() } as any)
          .returning();
        return row;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getFunnelAnalysis: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const stageCounts = await db
      .select({ stage: customerJourneySteps.status, count: count() })
      .from(customerJourneySteps)
      .groupBy(customerJourneySteps.status)
      .limit(100);
    const funnel = JOURNEY_STAGES.map((stage, i) => {
      const found = stageCounts.find(
        (s: Record<string, unknown>) => s.stage === stage
      );
      const stageCount = found ? Number(found.count) : 0;
      const prevCount =
        i > 0
          ? stageCounts.find(
              (s: Record<string, unknown>) => s.stage === JOURNEY_STAGES[i - 1]
            )?.count || 0
          : stageCount;
      return {
        stage,
        count: stageCount,
        conversionRate:
          prevCount > 0
            ? Math.round((stageCount / Number(prevCount)) * 100)
            : 0,
      };
    });
    return { funnel, stages: JOURNEY_STAGES };
  }),
  delete: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .delete(customerJourneySteps)
          .where(eq(customerJourneySteps.id, input.id));
        // Middleware fan-out (fail-open)
        await publishcustomerJourneyEventsCrudMiddleware("delete", `${Date.now()}`, { action: "delete" }).catch(() => {});

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
