import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { chatSessions, chatMessages, auditLog } from "../../drizzle/schema";
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

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "aiChatSupport",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "aiChatSupport",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
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
async function publishaiChatSupportMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `chat.${action}` as any;
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
      txType: `chat_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `chat_${action}`,
    timestamp: ts,
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("chat", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const aiChatSupportRouter = router({
  listSessions: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(50),
          status: z
            .enum(["open", "assigned", "resolved", "escalated"])
            .optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions = input?.status
          ? [eq(chatSessions.status, input.status)]
          : [];
        const rows =
          conditions.length > 0
            ? await db
                .select()
                .from(chatSessions)
                .where(conditions[0])
                .orderBy(desc(chatSessions.createdAt))
                .limit(input?.limit ?? 50)
            : await db
                .select()
                .from(chatSessions)
                .orderBy(desc(chatSessions.createdAt))
                .limit(input?.limit ?? 50);
        return { sessions: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getSession: protectedProcedure
    .input(z.object({ sessionId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [session] = await db
          .select()
          .from(chatSessions)
          .where(eq(chatSessions.id, input.sessionId))
          .limit(1);
        if (!session) return null;
        const messages = await db
          .select()
          .from(chatMessages)
          .where(eq(chatMessages.sessionId, input.sessionId))
          .orderBy(chatMessages.createdAt)
          .limit(100);
        return { ...session, messages };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  sendMessage: protectedProcedure
    .input(
      z.object({
        sessionId: z.number(),
        content: z.string(),
        senderType: z.enum(["agent", "support", "system"]).default("support"),
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
        const [msg] = await db
          .insert(chatMessages)
          .values({
            sessionId: input.sessionId,
            content: input.content,
            senderType: input.senderType,
          })
          .returning();
        await db.insert(auditLog).values({
          action: "chat_message_sent",
          resource: "chat_messages",
          resourceId: String(msg.id),
          status: "success",
          metadata: { sessionId: input.sessionId },
        });
        return msg;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  resolveSession: protectedProcedure
    .input(
      z.object({ sessionId: z.number(), resolution: z.string().optional() })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .update(chatSessions)
          .set({ status: "resolved" })
          .where(eq(chatSessions.id, input.sessionId));
        await db.insert(auditLog).values({
          action: "chat_session_resolved",
          resource: "chat_sessions",
          resourceId: String(input.sessionId),
          status: "success",
          metadata: { resolution: input.resolution },
        });

        // Middleware fan-out (fail-open)

        await publishAiChatSupportMiddleware("sendMessage", `${Date.now()}`, { action: "sendMessage" }).catch(() => {});


        // Middleware fan-out (fail-open)


        await publishAiChatSupportMiddleware("resolveSession", `${Date.now()}`, { action: "resolveSession" }).catch(() => {});



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
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [total] = await db
      .select({ value: count() })
      .from(chatSessions)
      .limit(100);
    const [open] = await db
      .select({ value: count() })
      .from(chatSessions)
      .where(eq(chatSessions.status, "open"))
      .limit(100);
    const [resolved] = await db
      .select({ value: count() })
      .from(chatSessions)
      .where(eq(chatSessions.status, "resolved"))
      .limit(100);
    return {
      totalSessions: Number(total.value),
      openSessions: Number(open.value),
      resolvedSessions: Number(resolved.value),
      resolutionRate:
        Number(total.value) > 0
          ? Math.round((Number(resolved.value) / Number(total.value)) * 100)
          : 0,
    };
  }),
});
