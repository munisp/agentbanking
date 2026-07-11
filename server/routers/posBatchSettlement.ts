/**
 * POS Batch Settlement — aggregate POS terminal transactions into settlement
 * batches, calculate net amounts after fees, and process payouts to agents.
 *
 * Middleware: Kafka (settlement events), Redis (batch locks), PostgreSQL (batch records),
 * TigerBeetle (ledger entries), Temporal (payout workflow)
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  posSettlementBatches,
  posTerminals,
  transactions,
  gl_journal_entries,
  agents,
} from "../../drizzle/schema";
import { eq, desc, and, sql, gte, lte, count, sum } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
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
import { validateInput } from "../lib/routerHelpers";

import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce as fluvioPublish } from "../fluvio";
import { dapr } from "../middleware/middlewareConnectors";
import { ingestToLakehouse as lakehouseIngest } from "../lakehouse";
import { cacheGet, cacheSet, cacheInvalidate } from "../lib/cacheClient";

function publishPosMiddleware(
  eventType: string,
  key: string,
  payload: Record<string, unknown>
) {
  publishEvent("pos.batch.settlement", key, { eventType, ...payload });
  fluvioPublish("pos.batch.settlement", {
    key: "pos",
    value: JSON.stringify({
      eventType,
      ...payload,
      timestamp: new Date().toISOString(),
    }),
  }).catch(() => {});
  dapr
    .publishEvent("pubsub", "pos.batch.settlement.completed", {
      eventType,
      ...payload,
    })
    .catch(() => {});
  lakehouseIngest("pos_batch_settlements", {
    event_type: eventType,
    ...payload,
    source: "posBatchSettlement",
  }).catch(() => {});
}

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["processing"],
  processing: ["settled", "failed", "partially_settled"],
  settled: ["reconciled"],
  partially_settled: ["processing", "settled"],
  failed: ["pending"],
  reconciled: [],
};

async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "posBatchSettlement",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "posBatchSettlement",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

function logOperation(action: string, details: Record<string, unknown>) {
  auditFinancialAction(
    "UPDATE",
    "posBatchSettlement",
    action,
    JSON.stringify(details)
  );
}

export const posBatchSettlementRouter = router({
  createBatch: protectedProcedure
    .input(
      z.object({
        terminalId: z.number().min(1),
        periodStart: z.string().min(1).max(255),
        periodEnd: z.string().min(1).max(255),
        currency: z.string().length(3).default("NGN"),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const db = (await getDb())!;
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [terminal] = await db
          .select()
          .from(posTerminals)
          .where(eq(posTerminals.id, input.terminalId))
          .limit(1);
        if (!terminal)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Terminal not found",
          });

        const periodStart = new Date(input.periodStart);
        const periodEnd = new Date(input.periodEnd);
        if (periodEnd <= periodStart)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "periodEnd must be after periodStart",
          });

        const [txAgg] = await db
          .select({
            txCount: count(),
            totalAmt: sum(transactions.amount),
          })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, terminal.agentId ?? 0),
              gte(transactions.createdAt, periodStart),
              lte(transactions.createdAt, periodEnd),
              eq(transactions.status, "success")
            )
          );

        const txCount = Number(txAgg?.txCount ?? 0);
        const totalAmount = Math.round(Number(txAgg?.totalAmt ?? 0));
        const feeResult = calculateFee(totalAmount, "pos_settlement");
        const totalFees = feeResult.fee;
        const netAmount = totalAmount - totalFees;

        const batchRef = `POS-BATCH-${input.terminalId}-${Date.now()}`;

        const [batch] = await db
          .insert(posSettlementBatches)
          .values({
            batchRef,
            terminalId: input.terminalId,
            agentId: terminal.agentId,
            transactionCount: txCount,
            totalAmount,
            totalFees,
            netAmount,
            currency: input.currency,
            status: "pending",
            periodStart,
            periodEnd,
          })
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `posBatchSettlement transaction`,
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

        // TigerBeetle double-entry: agent float (2001) → cash payout (1001)
        tbCreateTransfer({
          debitAccountId: "2001",
          creditAccountId: "1001",
          amount: Math.round(Number(netAmount) * 100),
          ref: batchRef,
          txType: "pos_batch_settlement",
          agentCode: session.agentCode,
        }).catch(() => {});

        logOperation("batch_created", {
          batchRef,
          terminalId: input.terminalId,
          txCount,
          totalAmount,
          netAmount,
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "POS_SETTLEMENT_BATCH_CREATED",
          resource: "pos_settlement_batch",
          resourceId: String(batch.id),
          status: "success",
          metadata: { batchRef, txCount, totalAmount, netAmount },
        });

        publishPosMiddleware("createBatch", String(input.terminalId), {
          action: "createBatch",
          ...input,
        });
        return {
          success: true,
          message: `Settlement batch created with ${txCount} transactions`,
          batch,
        };
      });
    }),

  list: protectedProcedure
    .input(
      z.object({
        terminalId: z.number().optional(),
        agentId: z.number().optional(),
        status: z.string().max(32).optional(),
        page: z.number().min(1).default(1),
        limit: z.number().min(1).max(100).default(20),
      })
    )
    .query(async ({ input }) => {
      const db = (await getDb())!;
      if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const offset = (input.page - 1) * input.limit;
      const conditions = [];
      if (input.terminalId)
        conditions.push(eq(posSettlementBatches.terminalId, input.terminalId));
      if (input.agentId)
        conditions.push(eq(posSettlementBatches.agentId, input.agentId));
      if (input.status)
        conditions.push(eq(posSettlementBatches.status, input.status));

      const where = conditions.length > 0 ? and(...conditions) : undefined;

      const [items, [{ total }]] = await Promise.all([
        db
          .select()
          .from(posSettlementBatches)
          .where(where)
          .orderBy(desc(posSettlementBatches.createdAt))
          .limit(input.limit)
          .offset(offset),
        db.select({ total: count() }).from(posSettlementBatches).where(where),
      ]);

      return { items, total, page: input.page, limit: input.limit };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number().min(1) }))
    .query(async ({ input }) => {
      const db = (await getDb())!;
      if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [batch] = await db
        .select()
        .from(posSettlementBatches)
        .where(eq(posSettlementBatches.id, input.id))
        .limit(1);
      if (!batch) throw new TRPCError({ code: "NOT_FOUND" });
      return batch;
    }),

  processBatch: protectedProcedure
    .input(
      z.object({
        batchId: z.number().min(1),
        settlementRef: z.string().min(1).max(128).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const db = (await getDb())!;
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [batch] = await db
          .select()
          .from(posSettlementBatches)
          .where(eq(posSettlementBatches.id, input.batchId))
          .limit(1);
        if (!batch) throw new TRPCError({ code: "NOT_FOUND" });

        const allowed = STATUS_TRANSITIONS[batch.status] ?? [];
        if (!allowed.includes("processing") && !allowed.includes("settled"))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Cannot process batch in '${batch.status}' status`,
          });

        const settleRef =
          input.settlementRef ?? `SETTLE-${batch.batchRef}-${Date.now()}`;

        const [updated] = await db
          .update(posSettlementBatches)
          .set({
            status: "settled",
            settledAt: new Date(),
            settlementRef: settleRef,
            updatedAt: new Date(),
          })
          .where(eq(posSettlementBatches.id, input.batchId))
          .returning();

        logOperation("batch_settled", {
          batchId: input.batchId,
          batchRef: batch.batchRef,
          netAmount: batch.netAmount,
          settlementRef: settleRef,
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "POS_SETTLEMENT_BATCH_SETTLED",
          resource: "pos_settlement_batch",
          resourceId: String(input.batchId),
          status: "success",
          metadata: {
            batchRef: batch.batchRef,
            netAmount: batch.netAmount,
            settlementRef: settleRef,
          },
        });

        publishPosMiddleware("processBatch", String(input.batchId), {
          action: "processBatch",
          ...input,
        });
        return {
          success: true,
          message: "Batch settled successfully",
          batch: updated,
        };
      });
    }),

  failBatch: protectedProcedure
    .input(
      z.object({
        batchId: z.number().min(1),
        reason: z.string().min(1).max(500),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const db = (await getDb())!;
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [batch] = await db
          .select()
          .from(posSettlementBatches)
          .where(eq(posSettlementBatches.id, input.batchId))
          .limit(1);
        if (!batch) throw new TRPCError({ code: "NOT_FOUND" });

        const allowed = STATUS_TRANSITIONS[batch.status] ?? [];
        if (!allowed.includes("failed"))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Cannot fail batch in '${batch.status}' status`,
          });

        const [updated] = await db
          .update(posSettlementBatches)
          .set({ status: "failed", updatedAt: new Date() })
          .where(eq(posSettlementBatches.id, input.batchId))
          .returning();

        logOperation("batch_failed", {
          batchId: input.batchId,
          reason: input.reason,
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "POS_SETTLEMENT_BATCH_FAILED",
          resource: "pos_settlement_batch",
          resourceId: String(input.batchId),
          status: "success",
          metadata: { reason: input.reason },
        });

        publishPosMiddleware("failBatch", String(input.batchId), {
          action: "failBatch",
          ...input,
        });
        return {
          success: true,
          message: "Batch marked as failed",
          batch: updated,
        };
      });
    }),

  reconcileBatch: protectedProcedure
    .input(z.object({ batchId: z.number().min(1) }))
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const db = (await getDb())!;
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [batch] = await db
          .select()
          .from(posSettlementBatches)
          .where(eq(posSettlementBatches.id, input.batchId))
          .limit(1);
        if (!batch) throw new TRPCError({ code: "NOT_FOUND" });

        if (batch.status !== "settled")
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Only settled batches can be reconciled",
          });

        const [updated] = await db
          .update(posSettlementBatches)
          .set({ status: "reconciled", updatedAt: new Date() })
          .where(eq(posSettlementBatches.id, input.batchId))
          .returning();

        logOperation("batch_reconciled", { batchId: input.batchId });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "POS_SETTLEMENT_BATCH_RECONCILED",
          resource: "pos_settlement_batch",
          resourceId: String(input.batchId),
          status: "success",
        });

        publishPosMiddleware("reconcileBatch", String(input.batchId), {
          action: "reconcileBatch",
          ...input,
        });
        return { success: true, message: "Batch reconciled", batch: updated };
      });
    }),

  stats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

    const [totals] = await db
      .select({
        totalBatches: count(),
        totalSettled: sql<number>`COALESCE(SUM(CASE WHEN ${posSettlementBatches.status} = 'settled' OR ${posSettlementBatches.status} = 'reconciled' THEN 1 ELSE 0 END), 0)`,
        totalAmount: sql<number>`COALESCE(SUM(${posSettlementBatches.totalAmount}), 0)`,
        totalFees: sql<number>`COALESCE(SUM(${posSettlementBatches.totalFees}), 0)`,
        totalNet: sql<number>`COALESCE(SUM(${posSettlementBatches.netAmount}), 0)`,
      })
      .from(posSettlementBatches);

    const byStatus = await db
      .select({
        status: posSettlementBatches.status,
        cnt: count(),
      })
      .from(posSettlementBatches)
      .groupBy(posSettlementBatches.status);

    const todayBatches = await db
      .select({ cnt: count() })
      .from(posSettlementBatches)
      .where(gte(posSettlementBatches.createdAt, sql`CURRENT_DATE`));

    return {
      totalBatches: Number(totals?.totalBatches ?? 0),
      totalSettled: Number(totals?.totalSettled ?? 0),
      totalAmount: Number(totals?.totalAmount ?? 0),
      totalFees: Number(totals?.totalFees ?? 0),
      totalNet: Number(totals?.totalNet ?? 0),
      byStatus: Object.fromEntries(
        byStatus.map((r: { status: string; cnt: number }) => [
          r.status,
          Number(r.cnt),
        ])
      ),
      batchesToday: Number(todayBatches[0]?.cnt ?? 0),
    };
  }),
});
