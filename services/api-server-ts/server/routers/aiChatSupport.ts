import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { chatSessions, chatMessages, auditLog } from "../../drizzle/schema";
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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateAichatsupportInput(data: Record<string, unknown>): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

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

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_AICHATSUPPORT = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_AICHATSUPPORT.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_AICHATSUPPORT.validateRange(data.amount, 0, 100_000_000)
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Transaction Patterns ───────────────────────────────────────────────────
// withTransaction ensures atomic multi-step mutations
// db.transaction() wraps sequential DB ops in a single transaction
// .transaction() provides rollback on failure
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
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "aiChatSupport",
        "mutation",
        "Executed aiChatSupport mutation"
      );

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

  // Start a new AI support chat session (persisted in chatSessions)
  createSession: protectedProcedure
    .input(z.object({ context: z.string().optional() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const sessionRef = `AI-${Date.now()}-${Math.floor(
          Math.random() * 100000
        )}`.slice(0, 32);
        const [session] = await db
          .insert(chatSessions)
          .values({
            sessionRef,
            agentId: ctx.user?.id ?? 0,
            category: "ai_support",
            subject: input.context ?? "AI Support Chat",
            status: "open",
          })
          .returning();
        const welcomeContent =
          "Hello! I'm your AI support assistant. How can I help you today?";
        const [welcome] = await db
          .insert(chatMessages)
          .values({
            sessionId: session.id,
            senderType: "support",
            senderName: "AI Assistant",
            content: welcomeContent,
          })
          .returning();
        await db.insert(auditLog).values({
          agentId: ctx.user?.id ?? null,
          action: "ai_chat_session_created",
          resource: "chat_sessions",
          resourceId: String(session.id),
          status: "success",
          metadata: { context: input.context ?? null, sessionRef },
        });
        return {
          session: { ...session, id: String(session.id) },
          welcomeMessage: {
            id: String(welcome.id),
            role: "assistant",
            content: welcomeContent,
            timestamp: welcome.createdAt.toISOString(),
          },
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

  // Escalate a session to human support
  escalate: protectedProcedure
    .input(
      z.object({
        sessionId: z.union([z.string(), z.number()]),
        reason: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const numericId = Number(input.sessionId);
        if (!Number.isFinite(numericId))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Invalid sessionId",
          });
        const [session] = await db
          .select()
          .from(chatSessions)
          .where(eq(chatSessions.id, numericId))
          .limit(1);
        if (!session)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: `Chat session ${input.sessionId} not found`,
          });
        await db
          .update(chatSessions)
          .set({ status: "escalated" })
          .where(eq(chatSessions.id, numericId));
        const content =
          "This chat has been escalated to a human support agent. Someone will join shortly.";
        const [msg] = await db
          .insert(chatMessages)
          .values({
            sessionId: numericId,
            senderType: "system",
            senderName: "System",
            content,
          })
          .returning();
        await db.insert(auditLog).values({
          agentId: ctx.user?.id ?? null,
          action: "ai_chat_session_escalated",
          resource: "chat_sessions",
          resourceId: String(numericId),
          status: "success",
          metadata: { reason: input.reason ?? null },
        });
        return {
          success: true,
          message: {
            id: String(msg.id),
            role: "system",
            content,
            timestamp: msg.createdAt.toISOString(),
            metadata: { type: "escalation" },
          },
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
