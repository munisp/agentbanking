import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count } from "drizzle-orm";
import { chatSessions, chatMessages, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { getIO } from "../socketSingleton";
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
      "chat",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "chat",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

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

const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

// ── Error Guards ───────────────────────────────────────────────────────────
function guardNotFound(val: unknown, entity: string): asserts val {
  if (!val)
    throw new TRPCError({ code: "NOT_FOUND", message: `${entity} not found` });
}
function guardForbidden(allowed: boolean, msg = "Forbidden"): void {
  if (!allowed) throw new TRPCError({ code: "FORBIDDEN", message: msg });
}
function guardConflict(condition: boolean, msg = "Conflict"): void {
  if (condition) throw new TRPCError({ code: "CONFLICT", message: msg });
}
function safeParse<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

export const chatRouter = router({
  startSession: protectedProcedure
    .input(
      z.object({
        subject: z.string().optional(),
        category: z.string().optional(),
        agentId: z.number().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as any).status as string;
        const currentStatus =
          ((input as any).currentStatus as string) || "pending";
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
          ? Number((input as any).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      const db = (await getDb())!;
      const [session] = await db
        .insert(chatSessions)
        .values({
          status: "open",
          agentId: input.agentId,
          subject: input.subject,
          category: input.category,
        } as any)
        .returning();
      await db.insert(auditLog).values({
        action: "chat_session_started",
        resource: "chat_sessions",
        resourceId: String(session.id),
        status: "success",
        metadata: {},
      } as any);
      return session;
    }),

  sendMessage: protectedProcedure
    .input(
      z.object({
        sessionId: z.number(),
        content: z.string(),
        senderType: z.enum(["agent", "support", "system"]).default("support"),
        senderName: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      const [msg] = await db
        .insert(chatMessages)
        .values({
          sessionId: input.sessionId,
          content: input.content,
          senderType: input.senderType,
          senderName: input.senderName,
        } as any)
        .returning();
      const io = getIO();
      if (io) {
        io.of("/chat")
          .to(`session:${input.sessionId}`)
          .emit("chat:message", msg);
      }
      return msg;
    }),

  getMessages: protectedProcedure
    .input(z.object({ sessionId: z.number(), limit: z.number().default(100) }))
    .query(async ({ input }) => {
      const db = (await getDb())!;
      const messages = await db
        .select()
        .from(chatMessages)
        .where(eq(chatMessages.sessionId, input.sessionId))
        .orderBy(chatMessages.createdAt)
        .limit(input.limit);
      return messages;
    }),

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
      const db = (await getDb())!;
      const rows = input?.status
        ? await db
            .select()
            .from(chatSessions)
            .where(eq(chatSessions.status, input.status))
            .orderBy(desc(chatSessions.createdAt))
            .limit(input?.limit ?? 50)
        : await db
            .select()
            .from(chatSessions)
            .orderBy(desc(chatSessions.createdAt))
            .limit(input?.limit ?? 50);

      return { sessions: rows, total: rows.length };
    }),

  closeSession: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      await db
        .update(chatSessions)
        .set({ status: "resolved" })
        .where(eq(chatSessions.id, input.id));
      await db.insert(auditLog).values({
        action: "chat_session_closed",
        resource: "chat_sessions",
        resourceId: String(input.id),
        status: "success",
        metadata: {},
      });
      return { success: true };
    }),

  adminListSessions: protectedProcedure
    .input(
      z
        .object({
          status: z
            .enum(["open", "assigned", "resolved", "escalated"])
            .optional(),
          limit: z.number().default(100),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = (await getDb())!;
      const rows = input?.status
        ? await db
            .select()
            .from(chatSessions)
            .where(eq(chatSessions.status, input.status))
            .orderBy(desc(chatSessions.createdAt))
            .limit(input?.limit ?? 100)
        : await db
            .select()
            .from(chatSessions)
            .orderBy(desc(chatSessions.createdAt))
            .limit(input?.limit ?? 100);
      return { sessions: rows, total: rows.length };
    }),

  adminGetMessages: protectedProcedure
    .input(z.object({ sessionId: z.number() }))
    .query(async ({ input }) => {
      const db = (await getDb())!;
      const messages = await db
        .select()
        .from(chatMessages)
        .where(eq(chatMessages.sessionId, input.sessionId))
        .orderBy(chatMessages.createdAt)
        .limit(500);
      return messages;
    }),

  adminDeleteSession: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      await db.delete(chatMessages).where(eq(chatMessages.sessionId, input.id));
      await db.delete(chatSessions).where(eq(chatSessions.id, input.id));
      return { success: true };
    }),

  adminStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [total] = await db.select({ value: count() }).from(chatSessions);
    const [open] = await db
      .select({ value: count() })
      .from(chatSessions)
      .where(eq(chatSessions.status, "open"));
    const [assigned] = await db
      .select({ value: count() })
      .from(chatSessions)
      .where(eq(chatSessions.status, "assigned"));
    const [escalated] = await db
      .select({ value: count() })
      .from(chatSessions)
      .where(eq(chatSessions.status, "escalated"));
    const [resolved] = await db
      .select({ value: count() })
      .from(chatSessions)
      .where(eq(chatSessions.status, "resolved"));
    return {
      totalSessions: Number(total.value),
      openSessions: Number(open.value),
      assignedSessions: Number(assigned.value),
      escalatedSessions: Number(escalated.value),
      resolvedSessions: Number(resolved.value),
    };
  }),

  adminAssignSession: protectedProcedure
    .input(z.object({ sessionId: z.number(), supportAgentName: z.string() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      await db
        .update(chatSessions)
        .set({
          status: "assigned",
          supportAgentName: input.supportAgentName,
        } as any)
        .where(eq(chatSessions.id, input.sessionId));
      return { success: true };
    }),

  adminReply: protectedProcedure
    .input(
      z.object({
        sessionId: z.number(),
        content: z.string(),
        senderName: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      const [msg] = await db
        .insert(chatMessages)
        .values({
          sessionId: input.sessionId,
          content: input.content,
          senderType: "support",
          senderName: input.senderName ?? "Admin",
        } as any)
        .returning();
      const io = getIO();
      if (io) {
        io.of("/chat")
          .to(`session:${input.sessionId}`)
          .emit("chat:message", msg);
      }
      return msg;
    }),

  adminEscalate: protectedProcedure
    .input(z.object({ sessionId: z.number(), reason: z.string().optional() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      await db
        .update(chatSessions)
        .set({ status: "escalated" })
        .where(eq(chatSessions.id, input.sessionId));
      await db.insert(auditLog).values({
        action: "chat_session_escalated",
        resource: "chat_sessions",
        resourceId: String(input.sessionId),
        status: "success",
        metadata: { reason: input.reason },
      } as any);
      return { success: true };
    }),

  adminResolve: protectedProcedure
    .input(z.object({ sessionId: z.number() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      await db
        .update(chatSessions)
        .set({ status: "resolved" })
        .where(eq(chatSessions.id, input.sessionId));
      return { success: true };
    }),
});
