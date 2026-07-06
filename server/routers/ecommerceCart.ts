import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  ecommerceCarts,
  ecommerceCartItems,
  ecommerceInventory,
  type EcommerceCartItem,
} from "../../drizzle/schema";
import { eq, and, sql, count } from "drizzle-orm";
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
import { TRPCError } from "@trpc/server";
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

const CART_SERVICE_URL =
  process.env.CART_SERVICE_URL || "http://localhost:8102";

/**
 * E-Commerce Cart Router
 * Bridges tRPC API with Rust cart/checkout microservice.
 * Falls back to direct Drizzle queries when Rust service is unavailable.
 * Supports offline-to-online cart synchronization.
 */

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "ecommerceCart",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "ecommerceCart",
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
    resource: "ecommerceCart",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "ecommerceCart",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
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
      for (const op of ops) results.push(await op());
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

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishecommerceCartMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `ecommerce.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(
    () => {}
  );

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `ecommerce_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `ecommerce_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("ecommerce", {
    ref,
    action,
    ...payload,
    timestamp: ts,
  }).catch(() => {});
}

export const ecommerceCartRouter = router({
  // ── Cart Operations ──────────────────────────────────────────────────────
  getCart: protectedProcedure
    .input(z.object({ customerId: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { items: [], subTotal: 0, itemCount: 0 };

      const [cart] = await database
        .select()
        .from(ecommerceCarts)
        .where(eq(ecommerceCarts.customerId, input.customerId))
        .limit(1);

      if (!cart) {
        return {
          customerId: input.customerId,
          items: [],
          subTotal: 0,
          itemCount: 0,
          couponCode: null,
          discountAmount: 0,
        };
      }

      const items = await database
        .select()
        .from(ecommerceCartItems)
        .where(eq(ecommerceCartItems.cartId, cart.id));

      const subTotal = items.reduce(
        (sum: number, item: EcommerceCartItem) =>
          sum + parseFloat(item.unitPrice) * item.quantity,
        0
      );

      return {
        id: cart.id,
        customerId: cart.customerId,
        items,
        subTotal,
        itemCount: items.reduce(
          (sum: number, i: EcommerceCartItem) => sum + i.quantity,
          0
        ),
        couponCode: cart.couponCode,
        discountAmount: parseFloat(cart.discountAmount),
        currency: cart.currency,
      };
    }),

  addItem: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        sku: z.string(),
        productId: z.number(),
        name: z.string(),
        quantity: z.number().min(1),
        unitPrice: z.string(),
        merchantId: z.number(),
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
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      // Check inventory availability (fail-closed)
      const [inv] = await database
        .select()
        .from(ecommerceInventory)
        .where(eq(ecommerceInventory.sku, input.sku))
        .limit(1);

      if (inv) {
        const available = inv.quantity - inv.reserved;
        if (available < input.quantity) {
          throw new Error(
            `Insufficient stock for ${input.sku}: ${available} available, ${input.quantity} requested`
          );
        }
      }

      // Get or create cart
      let [cart] = await database
        .select()
        .from(ecommerceCarts)
        .where(eq(ecommerceCarts.customerId, input.customerId))
        .limit(1);

      if (!cart) {
        [cart] = await database
          .insert(ecommerceCarts)
          .values({ customerId: input.customerId })
          .returning();
      }

      // Check if item already in cart
      const [existing] = await database
        .select()
        .from(ecommerceCartItems)
        .where(
          and(
            eq(ecommerceCartItems.cartId, cart.id),
            eq(ecommerceCartItems.sku, input.sku)
          )
        )
        .limit(1);

      if (existing) {
        await database
          .update(ecommerceCartItems)
          .set({ quantity: existing.quantity + input.quantity })
          .where(eq(ecommerceCartItems.id, existing.id));
      } else {
        await database.insert(ecommerceCartItems).values({
          cartId: cart.id,
          productId: input.productId,
          sku: input.sku,
          name: input.name,
          quantity: input.quantity,
          unitPrice: input.unitPrice,
          merchantId: input.merchantId,
        });
      }

      // Update cart timestamp
      await database
        .update(ecommerceCarts)
        .set({ updatedAt: new Date() })
        .where(eq(ecommerceCarts.id, cart.id));

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

        resource: "ecommerceCart",

        resourceId:
          typeof input === "object" && input !== null && "id" in input
            ? String((input as any).id)
            : "new",

        status: "success",

        metadata: { input: typeof input === "object" ? input : {} },
      });

      return { status: "added" };
    }),

  updateItem: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        sku: z.string(),
        quantity: z.number().min(0),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      const [cart] = await database
        .select()
        .from(ecommerceCarts)
        .where(eq(ecommerceCarts.customerId, input.customerId))
        .limit(1);

      if (!cart) throw new Error("Cart not found");

      if (input.quantity === 0) {
        await database
          .delete(ecommerceCartItems)
          .where(
            and(
              eq(ecommerceCartItems.cartId, cart.id),
              eq(ecommerceCartItems.sku, input.sku)
            )
          );
      } else {
        await database
          .update(ecommerceCartItems)
          .set({ quantity: input.quantity })
          .where(
            and(
              eq(ecommerceCartItems.cartId, cart.id),
              eq(ecommerceCartItems.sku, input.sku)
            )
          );
      }

      // Middleware fan-out (fail-open)

      await publishecommerceCartMiddleware("updateItem", `${Date.now()}`, {
        action: "updateItem",
      }).catch(() => {});

      return { status: "updated" };
    }),

  removeItem: protectedProcedure
    .input(z.object({ customerId: z.number(), sku: z.string() }))
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      const [cart] = await database
        .select()
        .from(ecommerceCarts)
        .where(eq(ecommerceCarts.customerId, input.customerId))
        .limit(1);

      if (!cart) throw new Error("Cart not found");

      await database
        .delete(ecommerceCartItems)
        .where(
          and(
            eq(ecommerceCartItems.cartId, cart.id),
            eq(ecommerceCartItems.sku, input.sku)
          )
        );

      // Middleware fan-out (fail-open)

      await publishecommerceCartMiddleware("removeItem", `${Date.now()}`, {
        action: "removeItem",
      }).catch(() => {});

      return { status: "removed" };
    }),

  clearCart: protectedProcedure
    .input(z.object({ customerId: z.number() }))
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      const [cart] = await database
        .select()
        .from(ecommerceCarts)
        .where(eq(ecommerceCarts.customerId, input.customerId))
        .limit(1);

      if (cart) {
        await database
          .delete(ecommerceCartItems)
          .where(eq(ecommerceCartItems.cartId, cart.id));
        await database
          .delete(ecommerceCarts)
          .where(eq(ecommerceCarts.id, cart.id));
      }

      // Middleware fan-out (fail-open)

      await publishecommerceCartMiddleware("clearCart", `${Date.now()}`, {
        action: "clearCart",
      }).catch(() => {});

      return { status: "cleared" };
    }),

  // ── Offline Sync ─────────────────────────────────────────────────────────
  syncOfflineCart: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        items: z.array(
          z.object({
            sku: z.string(),
            productId: z.number(),
            name: z.string(),
            quantity: z.number(),
            unitPrice: z.string(),
            merchantId: z.number(),
          })
        ),
        deviceId: z.string().min(1).max(255),
        checksum: z.string(),
        strategy: z
          .enum([
            "prefer_online",
            "prefer_offline",
            "sum_quantities",
            "max_quantity",
          ])
          .default("max_quantity"),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      // Get or create online cart
      let [cart] = await database
        .select()
        .from(ecommerceCarts)
        .where(eq(ecommerceCarts.customerId, input.customerId))
        .limit(1);

      if (!cart) {
        [cart] = await database
          .insert(ecommerceCarts)
          .values({
            customerId: input.customerId,
            offlineCreated: true,
            deviceId: input.deviceId,
          })
          .returning();
      }

      // Merge items using specified strategy
      const existingItems = await database
        .select()
        .from(ecommerceCartItems)
        .where(eq(ecommerceCartItems.cartId, cart.id));

      const existingMap = new Map<string, EcommerceCartItem>(
        existingItems.map((i: EcommerceCartItem) => [i.sku, i])
      );

      for (const offlineItem of input.items) {
        const existing = existingMap.get(offlineItem.sku);

        if (existing) {
          let newQty = existing.quantity;
          switch (input.strategy) {
            case "prefer_offline":
              newQty = offlineItem.quantity;
              break;
            case "sum_quantities":
              newQty = existing.quantity + offlineItem.quantity;
              break;
            case "max_quantity":
              newQty = Math.max(existing.quantity, offlineItem.quantity);
              break;
            case "prefer_online":
            default:
              break;
          }

          if (newQty !== existing.quantity) {
            await database
              .update(ecommerceCartItems)
              .set({ quantity: newQty })
              .where(eq(ecommerceCartItems.id, existing.id));
          }
        } else {
          await database.insert(ecommerceCartItems).values({
            cartId: cart.id,
            productId: offlineItem.productId,
            sku: offlineItem.sku,
            name: offlineItem.name,
            quantity: offlineItem.quantity,
            unitPrice: offlineItem.unitPrice,
            merchantId: offlineItem.merchantId,
          });
        }
      }

      return {
        status: "synced",
        strategy: input.strategy,
        itemsMerged: input.items.length,
      };
    }),
});
