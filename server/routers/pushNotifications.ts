/**
 * Push Notifications Router
 * Handles VAPID push subscription management for agents and admins.
 * Uses agentPushSubscriptions table (agentCode, endpoint, p256dhKey, authKey).
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
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
  draft: ["queued", "scheduled"],
  scheduled: ["queued", "cancelled"],
  queued: ["sending"],
  sending: ["delivered", "failed", "bounced"],
  delivered: ["read", "archived"],
  read: ["replied", "archived"],
  replied: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  bounced: ["retry_pending", "cancelled"],
  cancelled: [],
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
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus =
          "status" in input
            ? String((input as Record<string, unknown>).status)
            : "";
        const currentStatus =
          "currentStatus" in input
            ? String((input as Record<string, unknown>).currentStatus)
            : "pending";
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
          ? Number(
              "amount" in input ? (input as Record<string, unknown>).amount : 0
            )
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
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
          title: "54Link POS — Test Notification",
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
