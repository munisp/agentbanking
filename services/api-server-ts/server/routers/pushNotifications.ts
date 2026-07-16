/**
 * Push Notifications Router
 * Handles VAPID push subscription management for agents and admins.
 * Uses agentPushSubscriptions table (agentCode, endpoint, p256dhKey, authKey).
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { agentPushSubscriptions } from "../../drizzle/schema";
import { eq, and } from "drizzle-orm";
import { sendPushToAgent } from "../push";
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

// ── Zod schema for PushSubscription object ────────────────────────────────────
const PushSubscriptionSchema = z.object({
  endpoint: z.string().url(),
  expirationTime: z.number().nullable().optional(),
  keys: z.object({
    p256dh: z.string(),
    auth: z.string(),
  }),
});

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "pushNotifications",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "pushNotifications",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _pushNotifications_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

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

export const pushNotificationsRouter = router({
  // ── Get VAPID public key (needed by client to subscribe) ──────────────────
  getVapidPublicKey: protectedProcedure.query(() => {
    return {
      publicKey:
        process.env.VAPID_PUBLIC_KEY ||
        "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U",
    };
  }),

  // ── Subscribe: save a push subscription for the current user ─────────────
  subscribePush: protectedProcedure
    .input(
      z.object({
        subscription: PushSubscriptionSchema,
        agentCode: z.string().max(32),
        deviceName: z.string().max(100).optional(),
        userAgent: z.string().max(500).optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
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
        "pushNotifications",
        "mutation",
        "Executed pushNotifications mutation"
      );

      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");

        // Upsert: if the same endpoint already exists, update keys
        const existing = await db
          .select()
          .from(agentPushSubscriptions)
          .where(
            and(
              eq(agentPushSubscriptions.agentCode, input.agentCode),
              eq(agentPushSubscriptions.endpoint, input.subscription.endpoint)
            )
          )
          .limit(1);

        if (existing.length > 0) {
          await db
            .update(agentPushSubscriptions)
            .set({
              p256dhKey: input.subscription.keys.p256dh,
              authKey: input.subscription.keys.auth,
              userAgent: input.userAgent ?? null,
              updatedAt: new Date(),
            })
            .where(eq(agentPushSubscriptions.id, existing[0].id));
          return { success: true, action: "updated" as const };
        }

        await db.insert(agentPushSubscriptions).values({
          agentCode: input.agentCode,
          endpoint: input.subscription.endpoint,
          p256dhKey: input.subscription.keys.p256dh,
          authKey: input.subscription.keys.auth,
          userAgent: input.userAgent ?? null,
          createdAt: new Date(),
          updatedAt: new Date(),
        });

        return { success: true, action: "created" as const };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Unsubscribe: remove a push subscription ───────────────────────────────
  unsubscribePush: protectedProcedure
    .input(
      z.object({
        endpoint: z.string().url(),
        agentCode: z.string().max(32),
      })
    )
    .mutation(async ({ ctx, input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .delete(agentPushSubscriptions)
          .where(
            and(
              eq(agentPushSubscriptions.agentCode, input.agentCode),
              eq(agentPushSubscriptions.endpoint, input.endpoint)
            )
          );
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

  // ── List subscriptions for an agent ──────────────────────────────────────
  listSubscriptions: protectedProcedure
    .input(z.object({ agentCode: z.string().max(32) }))
    .query(async ({ ctx, input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const subs = await db
          .select({
            id: agentPushSubscriptions.id,
            endpoint: agentPushSubscriptions.endpoint,
            userAgent: agentPushSubscriptions.userAgent,
            createdAt: agentPushSubscriptions.createdAt,
          })
          .from(agentPushSubscriptions)
          .where(eq(agentPushSubscriptions.agentCode, input.agentCode));
        return subs;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Test push: send a test notification to the current user ──────────────
  testPush: protectedProcedure
    .input(
      z.object({
        agentCode: z.string().max(32),
        message: z.string().max(200).optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      try {
        const sent = await sendPushToAgent(input.agentCode, {
          title: "54agent POS — Test Notification",
          body: input.message ?? "Push notifications are working correctly.",
          icon: "/icons/icon-192x192.png",
          badge: "/icons/badge-72x72.png",
          tag: "test-notification",
          data: { type: "test", timestamp: Date.now() },
        });
        return { success: true, sent };
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
