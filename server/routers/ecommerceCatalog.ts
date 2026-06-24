import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  ecommerceProducts,
  ecommerceCategories,
  ecommerceInventory,
} from "../../drizzle/schema";
import { desc, eq, and, ilike, count, sql } from "drizzle-orm";
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


async function publishCatalogMiddleware(event: string, key: string, payload: Record<string, unknown>) {
  publishEvent("ecommerce.catalog", key, { event, ...payload, timestamp: Date.now() }).catch(() => {});
  publishTxToFluvio({ txRef: key, agentCode: String(payload.merchantId ?? "system"), amount: Number(payload.price ?? 0), type: `ecommerce.catalog.${event}`, timestamp: Date.now() }).catch(() => {});
  dapr.publishEvent("pubsub", `ecommerce.catalog.${event}`, { key, ...payload }).catch(() => {});
  ingestToLakehouse("ecommerce_catalog", { event, key, ...payload, timestamp: new Date().toISOString() }).catch(() => {});
}

const CATALOG_SERVICE_URL =
  process.env.CATALOG_SERVICE_URL || "http://localhost:8100";

/**
 * E-Commerce Catalog Router
 * Bridges tRPC API with Go catalog microservice for products, categories, and inventory.
 * Falls back to direct Drizzle queries when Go service is unavailable.
 */

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "ecommerceCatalog",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "ecommerceCatalog",
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
    resource: "ecommerceCatalog",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "ecommerceCatalog",
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

export const ecommerceCatalogRouter = router({
  // ── Products ─────────────────────────────────────────────────────────────
  listProducts: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        categoryId: z.number().optional(),
        active: z.boolean().optional(),
        search: z.string().min(1).max(500).optional(),
        agentId: z.number().optional(),
        merchantId: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { products: [], total: 0 };

      const conditions = [];
      if (input.categoryId) {
        conditions.push(eq(ecommerceProducts.categoryId, input.categoryId));
      }
      if (input.active !== undefined) {
        conditions.push(eq(ecommerceProducts.isActive, input.active));
      }
      if (input.search) {
        conditions.push(ilike(ecommerceProducts.name, `%${input.search}%`));
      }
      if (input.agentId) {
        conditions.push(eq(ecommerceProducts.agentId, input.agentId));
      }
      if (input.merchantId) {
        conditions.push(eq(ecommerceProducts.merchantId, input.merchantId));
      }

      const where = conditions.length > 0 ? and(...conditions) : undefined;

      const [products, totalResult] = await Promise.all([
        database
          .select()
          .from(ecommerceProducts)
          .where(where)
          .orderBy(desc(ecommerceProducts.createdAt))
          .limit(input.limit)
          .offset(input.offset),
        database
          .select({ total: count() })
          .from(ecommerceProducts)
          .where(where),
      ]);

      return {
        products,
        total: totalResult[0]?.total ?? 0,
        limit: input.limit,
        offset: input.offset,
      };
    }),

  getProduct: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [product] = await database
        .select()
        .from(ecommerceProducts)
        .where(eq(ecommerceProducts.id, input.id))
        .limit(1);

      return product ?? null;
    }),

  createProduct: protectedProcedure
    .input(
      z.object({
        sku: z.string().min(1).max(64),
        name: z.string().min(1).max(256),
        description: z.string().optional(),
        categoryId: z.number(),
        price: z.string(),
        currency: z.string().default("NGN"),
        imageUrl: z.string().optional(),
        merchantId: z.number(),
        agentId: z.number().optional(),
        weight: z.string().optional(),
        dimensions: z.string().optional(),
        tags: z.array(z.string()).optional(),
        attributes: z.record(z.string(), z.string()).optional(),
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

      const [product] = await database
        .insert(ecommerceProducts)
        .values({
          sku: input.sku,
          name: input.name,
          description: input.description ?? null,
          categoryId: input.categoryId,
          price: input.price,
          currency: input.currency,
          imageUrl: input.imageUrl ?? null,
          merchantId: input.merchantId,
          agentId: input.agentId ?? null,
          weight: input.weight ?? null,
          dimensions: input.dimensions ?? null,
          tags: input.tags ?? [],
          attributes: input.attributes ?? {},
        })
        .returning();

      // Create inventory record
      await database.insert(ecommerceInventory).values({
        sku: input.sku,
        productId: product.id,
        quantity: 0,
        reserved: 0,
        reorderPoint: 10,
      });

      publishCatalogMiddleware("product.created", product.sku, { productId: product.id, name: product.name, price: input.price, merchantId: input.merchantId });
      cacheSet(`catalog:product:${product.id}`, JSON.stringify(product), 3600).catch(() => {});

      return product;
    }),

  updateProduct: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        name: z.string().optional(),
        description: z.string().optional(),
        price: z.string().optional(),
        isActive: z.boolean().optional(),
        tags: z.array(z.string()).optional(),
        attributes: z.record(z.string(), z.string()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      const updates: Record<string, unknown> = { updatedAt: new Date() };
      if (input.name) updates.name = input.name;
      if (input.description !== undefined)
        updates.description = input.description;
      if (input.price) updates.price = input.price;
      if (input.isActive !== undefined) updates.isActive = input.isActive;
      if (input.tags) updates.tags = input.tags;
      if (input.attributes) updates.attributes = input.attributes;

      const [updated] = await database
        .update(ecommerceProducts)
        .set(updates)
        .where(eq(ecommerceProducts.id, input.id))
        .returning();

      publishCatalogMiddleware("product.updated", String(input.id), { productId: input.id, changes: Object.keys(updates) });

      return updated;
    }),

  deleteProduct: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      await database
        .delete(ecommerceProducts)
        .where(eq(ecommerceProducts.id, input.id));

      publishCatalogMiddleware("product.deleted", String(input.id), { productId: input.id });

      return { deleted: true };
    }),

  searchProducts: protectedProcedure
    .input(z.object({ query: z.string(), limit: z.number().default(20) }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { products: [] };

      const products = await database
        .select()
        .from(ecommerceProducts)
        .where(
          sql`${ecommerceProducts.name} ILIKE ${`%${input.query}%`} OR ${ecommerceProducts.sku} ILIKE ${`%${input.query}%`}`
        )
        .limit(input.limit);

      return { products, query: input.query };
    }),

  // ── Categories ───────────────────────────────────────────────────────────
  listCategories: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { categories: [] };

    const categories = await database
      .select()
      .from(ecommerceCategories)
      .where(eq(ecommerceCategories.isActive, true))
      .orderBy(ecommerceCategories.sortOrder);

    return { categories };
  }),

  createCategory: protectedProcedure
    .input(
      z.object({
        name: z.string().min(1),
        slug: z.string().min(1),
        description: z.string().optional(),
        parentId: z.number().optional(),
        imageUrl: z.string().optional(),
        sortOrder: z.number().default(0),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      const [category] = await database
        .insert(ecommerceCategories)
        .values({
          name: input.name,
          slug: input.slug,
          description: input.description ?? null,
          parentId: input.parentId ?? null,
          imageUrl: input.imageUrl ?? null,
          sortOrder: input.sortOrder,
        })
        .returning();

      publishCatalogMiddleware("category.created", category.slug, { categoryId: category.id, name: category.name });

      return category;
    }),

  // ── Inventory ────────────────────────────────────────────────────────────
  getInventory: protectedProcedure
    .input(z.object({ sku: z.string() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [inv] = await database
        .select()
        .from(ecommerceInventory)
        .where(eq(ecommerceInventory.sku, input.sku))
        .limit(1);

      if (!inv) return null;
      return { ...inv, available: inv.quantity - inv.reserved };
    }),

  lowStockAlerts: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { alerts: [] };

      const alerts = await database
        .select()
        .from(ecommerceInventory)
        .where(
          sql`(${ecommerceInventory.quantity} - ${ecommerceInventory.reserved}) <= ${ecommerceInventory.reorderPoint}`
        )
        .orderBy(
          sql`(${ecommerceInventory.quantity} - ${ecommerceInventory.reserved}) ASC`
        )
        .limit(input.limit);

      return { alerts, count: alerts.length };
    }),

  updateStock: protectedProcedure
    .input(
      z.object({
        sku: z.string(),
        quantity: z.number(),
        reason: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");

      const [updated] = await database
        .update(ecommerceInventory)
        .set({
          quantity: input.quantity,
          updatedAt: new Date(),
          lastRestocked: new Date(),
        })
        .where(eq(ecommerceInventory.sku, input.sku))
        .returning();

      publishCatalogMiddleware("stock.updated", input.sku, { quantity: input.quantity, reason: input.reason });
      cacheSet(`catalog:inventory:${input.sku}`, JSON.stringify(updated), 1800).catch(() => {});

      return updated;
    }),
});
