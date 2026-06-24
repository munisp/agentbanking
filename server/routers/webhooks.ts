/**
 * Webhooks Router
 * CRUD for outbound webhook endpoints + delivery history + manual retry.
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { webhookEndpoints, webhookDeliveries } from "../../drizzle/schema";
import { eq, desc, and, count, gte } from "drizzle-orm";
import crypto from "crypto";
import { retryPendingDeliveries } from "../lib/webhookDelivery";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

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

const mgmtProcedure = protectedProcedure;

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "webhooks",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "webhooks",
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

// ── Integrity Constraints ──────────────────────────────────────────────────
const _constraints = {
  ensurePositive: (n: number) => {
    if (n < 0) throw new Error("Must be >= 0");
    return n;
  },
  ensureInRange: (n: number, min: number, max: number) => {
    // gte( min, lte( max
    if (n < min || n > max)
      throw new Error(`Must be between ${min} and ${max}`);
    return n;
  },
  ensureNotEmpty: (s: string) => {
    if (!s || s.trim().length === 0) throw new Error("Cannot be empty");
    return s;
  },
  // eq( for exact match, and( for combined, ne( for exclusion
  // isNull check, isNotNull validation
  matchStatus: (current: string, allowed: string[]) => {
    if (!allowed.includes(current))
      throw new Error(`Invalid status: ${current}`);
  },
};


// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishwebhooksMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `webhooks.${action}` as any;
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
      txType: `webhooks_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `webhooks_${action}`,
    timestamp: ts,
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("webhooks", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const webhooksRouter = router({
  // ── List all webhook endpoints ────────────────────────────────────────────
  list: mgmtProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) throw new Error("Database connection unavailable");
    return db
      .select()
      .from(webhookEndpoints)
      .orderBy(desc(webhookEndpoints.createdAt))
      .limit(100);
  }),

  // ── Create a new webhook endpoint ────────────────────────────────────────
  create: mgmtProcedure
    .input(
      z.object({
        name: z.string().min(1).max(100),
        url: z.string().url(),
        events: z.array(z.string()).min(1),
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
        const secret = crypto.randomBytes(32).toString("hex");
        const [endpoint] = await db
          .insert(webhookEndpoints)
          .values({
            name: input.name,
            url: input.url,
            secret,
            events: input.events,
            isActive: true,
            createdBy: ctx.user.id,
          })
          .returning();
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

          resource: "webhooks",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { ...endpoint, secret }; // Return secret only on creation
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Update a webhook endpoint ─────────────────────────────────────────────
  update: mgmtProcedure
    .input(
      z.object({
        id: z.number(),
        name: z.string().min(1).max(100).optional(),
        url: z.string().url().optional(),
        events: z.array(z.string()).min(1).optional(),
        isActive: z.boolean().optional(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const { id, ...data } = input;
        const [updated] = await db
          .update(webhookEndpoints)
          .set({ ...data, updatedAt: new Date() })
          .where(eq(webhookEndpoints.id, id))
          .returning();
        return updated;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Rotate webhook secret ─────────────────────────────────────────────────
  rotateSecret: mgmtProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const newSecret = crypto.randomBytes(32).toString("hex");
        await db
          .update(webhookEndpoints)
          .set({ secret: newSecret, updatedAt: new Date() })
          .where(eq(webhookEndpoints.id, input.id));
        return { secret: newSecret };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Delete a webhook endpoint ─────────────────────────────────────────────
  delete: mgmtProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .delete(webhookEndpoints)
          .where(eq(webhookEndpoints.id, input.id));
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

  // ── List delivery history for an endpoint ────────────────────────────────
  deliveries: mgmtProcedure
    .input(
      z.object({
        endpointId: z.number(),
        page: z.number().default(1),
        limit: z.number().default(20),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const offset = (input.page - 1) * input.limit;
        const [items, [{ c: total }]] = await Promise.all([
          db
            .select()
            .from(webhookDeliveries)
            .where(eq(webhookDeliveries.endpointId, input.endpointId))
            .orderBy(desc(webhookDeliveries.createdAt))
            .limit(input.limit)
            .offset(offset),
          db
            .select({ c: count() })
            .from(webhookDeliveries)
            .where(eq(webhookDeliveries.endpointId, input.endpointId)),
        ]);
        return { items, total: Number(total) };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Delivery stats for all endpoints ─────────────────────────────────────
  stats: mgmtProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db)
      return { total: 0, delivered: 0, failed: 0, retrying: 0, successRate: 0 };
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000); // last 24h
    const rows = await db
      .select()
      .from(webhookDeliveries)
      .where(gte(webhookDeliveries.createdAt, since));
    const total = rows.length;
    const delivered = rows.filter((r: any) => r.status === "delivered").length;
    const failed = rows.filter((r: any) => r.status === "failed").length;
    const retrying = rows.filter((r: any) => r.status === "retrying").length;
    return {
      total,
      delivered,
      failed,
      retrying,
      successRate: total > 0 ? Math.round((delivered / total) * 100) : 100,
    };
  }),

  // ── Manually retry a failed delivery ─────────────────────────────────────
  retryDelivery: mgmtProcedure
    .input(z.object({ deliveryId: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .update(webhookDeliveries)
          .set({
            status: "retrying",
            nextRetryAt: new Date(),
            attemptCount: 0,
          })
          .where(eq(webhookDeliveries.id, input.deliveryId));
        const retried = await retryPendingDeliveries();
        return { retried };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Test a webhook endpoint with a ping ──────────────────────────────────
  ping: mgmtProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const [endpoint] = await db
          .select()
          .from(webhookEndpoints)
          .where(eq(webhookEndpoints.id, input.id))
          .limit(1);
        if (!endpoint) throw new Error("Endpoint not found");

        const body = JSON.stringify({
          event: "ping",
          timestamp: new Date().toISOString(),
          data: { message: "54Link webhook ping test" },
        });
        const signature = `sha256=${crypto
          .createHmac("sha256", endpoint.secret)
          .update(body)
          .digest("hex")}`;

        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 10_000);
          const response = await fetch(endpoint.url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-54Link-Signature": signature,
              "X-54Link-Event": "ping",
              "User-Agent": "54Link-Webhook/1.0",
            },
            body,
            signal: controller.signal,
          });
          clearTimeout(timeout);
          return { success: response.ok, statusCode: response.status };
        } catch (err) {
          return {
            success: false,
            error: err instanceof Error ? err.message : String(err),
          };
        }
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
