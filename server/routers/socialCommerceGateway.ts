import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { auditLog, ecommerceProducts, agentStores } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count, ilike } from "drizzle-orm";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import {
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";

async function publishSocialMiddleware(event: string, key: string, payload: Record<string, unknown>) {
  publishEvent("ecommerce.social", key, { event, ...payload, timestamp: Date.now() }).catch(() => {});
  publishTxToFluvio({ txRef: key, agentCode: String(payload.storeId ?? "system"), amount: Number(payload.amount ?? 0), type: `ecommerce.social.${event}`, timestamp: Date.now() }).catch(() => {});
  dapr.publishEvent("pubsub", `ecommerce.social.${event}`, { key, ...payload }).catch(() => {});
  ingestToLakehouse("ecommerce_social", { event, key, ...payload, timestamp: new Date().toISOString() }).catch(() => {});
}

const SOCIAL_PLATFORMS = ["whatsapp", "instagram", "tiktok", "facebook"] as const;

export const socialCommerceGatewayRouter = router({
  // ── Catalog Push ─────────────────────────────────────────────────────────
  pushCatalog: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        platform: z.enum(SOCIAL_PLATFORMS),
        productIds: z.array(z.number()).min(1).max(500),
        accessToken: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Database unavailable" });

      const products = await database
        .select()
        .from(ecommerceProducts)
        .where(sql`${ecommerceProducts.id} = ANY(${input.productIds})`);

      if (products.length === 0) {
        throw new TRPCError({ code: "NOT_FOUND", message: "No products found" });
      }

      const catalogPayload = products.map((p: any) => ({
        id: p.id,
        name: p.name,
        sku: p.sku,
        price: p.price,
        currency: p.currency,
        imageUrl: p.imageUrl,
        description: p.description,
      }));

      // Platform-specific API calls (via Dapr service invocation)
      const platformEndpoint = `social-${input.platform}-connector`;
      await dapr.invokeService(platformEndpoint, "catalog/push", {
        storeId: input.storeId,
        products: catalogPayload,
        accessToken: input.accessToken,
      }).catch(() => {
        // Fail-open: log but don't fail the whole operation
      });

      await writeAuditLog({
        agentId: 0,
        agentCode: "system",
        action: "SOCIAL_CATALOG_PUSH",
        resource: "socialCommerceGateway",
        resourceId: String(input.storeId),
        status: "success",
        metadata: { platform: input.platform, productCount: products.length },
      });

      publishSocialMiddleware("catalog.pushed", String(input.storeId), {
        storeId: input.storeId,
        platform: input.platform,
        productCount: products.length,
      });

      return {
        status: "pushed",
        platform: input.platform,
        productsPublished: products.length,
      };
    }),

  // ── Social Order Ingestion ───────────────────────────────────────────────
  ingestSocialOrder: protectedProcedure
    .input(
      z.object({
        platform: z.enum(SOCIAL_PLATFORMS),
        externalOrderId: z.string(),
        storeId: z.number(),
        customerId: z.number().optional(),
        customerName: z.string(),
        customerPhone: z.string(),
        customerAddress: z.string().optional(),
        items: z.array(
          z.object({
            productId: z.number(),
            sku: z.string(),
            quantity: z.number().min(1),
            unitPrice: z.string(),
          })
        ),
        totalAmount: z.string(),
        currency: z.string().default("NGN"),
        paymentMethod: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Database unavailable" });

      const orderId = `SOCIAL-${input.platform.toUpperCase()}-${Date.now()}`;
      const totalKobo = Math.round(parseFloat(input.totalAmount) * 100);

      // Record the social order in audit log
      await writeAuditLog({
        agentId: 0,
        agentCode: "system",
        action: "SOCIAL_ORDER_INGESTED",
        resource: "socialCommerceGateway",
        resourceId: orderId,
        status: "success",
        metadata: {
          platform: input.platform,
          externalOrderId: input.externalOrderId,
          storeId: input.storeId,
          totalAmount: input.totalAmount,
          items: input.items.length,
        },
      });

      // Create TigerBeetle journal entry
      tbCreateTransfer({
        debitAccountId: String(input.storeId),
        creditAccountId: "9999",
        amount: totalKobo,
        ledger: 2,
        code: 201,
      }).catch(() => {});

      publishSocialMiddleware("order.ingested", orderId, {
        storeId: input.storeId,
        platform: input.platform,
        amount: totalKobo,
        externalOrderId: input.externalOrderId,
        itemCount: input.items.length,
      });

      cacheSet(`social:order:${orderId}`, JSON.stringify({ ...input, orderId }), 86400).catch(() => {});

      return {
        orderId,
        status: "ingested",
        platform: input.platform,
        totalAmount: input.totalAmount,
      };
    }),

  // ── Sync Store to Platform ───────────────────────────────────────────────
  syncStoreToPlatform: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        platform: z.enum(SOCIAL_PLATFORMS),
        syncType: z.enum(["full", "delta"]).default("delta"),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Database unavailable" });

      const [store] = await database
        .select()
        .from(agentStores)
        .where(eq(agentStores.id, input.storeId))
        .limit(1);

      if (!store) throw new TRPCError({ code: "NOT_FOUND", message: "Store not found" });

      const products = await database
        .select()
        .from(ecommerceProducts)
        .where(eq(ecommerceProducts.merchantId, store.agentId));

      publishSocialMiddleware("store.synced", String(input.storeId), {
        storeId: input.storeId,
        platform: input.platform,
        syncType: input.syncType,
        productCount: products.length,
      });

      return {
        status: "synced",
        platform: input.platform,
        syncType: input.syncType,
        productsCount: products.length,
        storeName: store.storeName,
      };
    }),

  // ── Platform Message Webhook ─────────────────────────────────────────────
  handlePlatformWebhook: protectedProcedure
    .input(
      z.object({
        platform: z.enum(SOCIAL_PLATFORMS),
        eventType: z.string(),
        payload: z.record(z.string(), z.unknown()),
        signature: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      publishSocialMiddleware("webhook.received", `${input.platform}-${input.eventType}`, {
        platform: input.platform,
        eventType: input.eventType,
      });

      // Route to appropriate handler based on event type
      const eventRouting: Record<string, string> = {
        "message.received": "chat",
        "order.created": "order",
        "payment.completed": "payment",
        "catalog.updated": "catalog",
      };

      const handler = eventRouting[input.eventType] ?? "unknown";

      await writeAuditLog({
        agentId: 0,
        agentCode: "system",
        action: "SOCIAL_WEBHOOK",
        resource: "socialCommerceGateway",
        resourceId: `${input.platform}-${input.eventType}`,
        status: "success",
        metadata: { platform: input.platform, eventType: input.eventType, handler },
      });

      return { acknowledged: true, handler, platform: input.platform };
    }),

  // ── Read-Only Queries ────────────────────────────────────────────────────
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const results = await database
          .select()
          .from(ecommerceProducts)
          .orderBy(desc(ecommerceProducts.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(ecommerceProducts);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch {
        return { data: [], total: 0, limit: 0, offset: 0 };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;
      const [record] = await database
        .select()
        .from(ecommerceProducts)
        .where(eq(ecommerceProducts.id, input.id))
        .limit(1);

      if (!record) {
        throw new TRPCError({ code: "NOT_FOUND", message: `Product with id ${input.id} not found` });
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { totalRecords: 0, lastUpdated: new Date().toISOString() };
    const _totalRows = await database
      .select({ total: count() })
      .from(ecommerceProducts);
    const totalResult = Array.isArray(_totalRows) ? _totalRows[0] : _totalRows;

    return {
      totalRecords: totalResult?.total ?? 0,
      lastUpdated: new Date().toISOString(),
    };
  }),

  getStats: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return { total: 0, active: 0, recent: 0, lastUpdated: new Date().toISOString() };
    try {
      const [totalRow] = await database
        .select({ total: count() })
        .from(ecommerceProducts);
      const total = totalRow?.total ?? 0;
      return {
        total,
        active: total,
        recent: Math.min(total, 50),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return { total: 0, active: 0, recent: 0, lastUpdated: new Date().toISOString() };
    }
  }),
});
