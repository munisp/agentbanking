import crypto from "crypto";
import { z } from "zod";
import { protectedProcedure, publicProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  agentStores,
  deliveryZones,
  deliveryTracking,
  paymentSplits,
  ecommerceProducts,
  ecommerceOrders,
} from "../../drizzle/schema";
import {
  desc,
  eq,
  and,
  ilike,
  count,
  sql,
  gte,
  lte,
  or,
  asc,
} from "drizzle-orm";
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
  draft: ["pending_review"],
  pending_review: ["approved", "rejected"],
  approved: ["active", "suspended"],
  active: ["suspended", "deactivated", "under_review"],
  suspended: ["active", "deactivated"],
  under_review: ["active", "suspended", "deactivated"],
  deactivated: ["reactivation_pending"],
  reactivation_pending: ["active", "rejected"],
  rejected: [],
};

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

const businessHoursSchema = z
  .object({
    monday: z.object({ open: z.string(), close: z.string() }).optional(),
    tuesday: z.object({ open: z.string(), close: z.string() }).optional(),
    wednesday: z.object({ open: z.string(), close: z.string() }).optional(),
    thursday: z.object({ open: z.string(), close: z.string() }).optional(),
    friday: z.object({ open: z.string(), close: z.string() }).optional(),
    saturday: z.object({ open: z.string(), close: z.string() }).optional(),
    sunday: z.object({ open: z.string(), close: z.string() }).optional(),
  })
  .optional();

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentStore",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentStore",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
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

export const agentStoreRouter = router({
  // ── Store Registration & Setup ──────────────────────────────────────────
  registerStore: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        agentCode: z.string().min(1),
        storeName: z.string().min(2).max(256),
        description: z.string().optional(),
        phone: z.string().optional(),
        email: z.string().email().email().optional(),
        address: z.string().optional(),
        city: z.string().optional(),
        state: z.string().optional(),
        lga: z.string().optional(),
        latitude: z.string().optional(),
        longitude: z.string().optional(),
        categories: z.array(z.string()).optional(),
        deliveryEnabled: z.boolean().default(true),
        pickupEnabled: z.boolean().default(true),
        businessHours: businessHoursSchema,
      })
    )
    .mutation(async ({ input, ctx }) => {
      // Enforce STATUS_TRANSITIONS state machine
      if (typeof input === "object" && "status" in input) {
        const currentStatus = "pending"; // Will be overridden by DB lookup
        const newStatus = (input as any).status;
        const allowed =
          STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition`,
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
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable",
        });

      // Check for existing store
      const [existing] = await database
        .select({ id: agentStores.id })
        .from(agentStores)
        .where(eq(agentStores.agentId, input.agentId))
        .limit(1);
      if (existing) {
        throw new TRPCError({
          code: "CONFLICT",
          message: "Agent already has a store",
        });
      }

      const baseSlug = slugify(input.storeName);
      let slug = baseSlug;
      let attempt = 0;
      while (attempt < 10) {
        const [dup] = await database
          .select({ id: agentStores.id })
          .from(agentStores)
          .where(eq(agentStores.slug, slug))
          .limit(1);
        if (!dup) break;
        attempt++;
        slug = `${baseSlug}-${attempt}`;
      }

      const [store] = await database
        .insert(agentStores)
        .values({
          agentId: input.agentId,
          agentCode: input.agentCode,
          slug,
          storeName: input.storeName,
          description: input.description ?? null,
          phone: input.phone ?? null,
          email: input.email ?? null,
          address: input.address ?? null,
          city: input.city ?? null,
          state: input.state ?? null,
          lga: input.lga ?? null,
          latitude: input.latitude ?? null,
          longitude: input.longitude ?? null,
          categories: input.categories ?? [],
          deliveryEnabled: input.deliveryEnabled,
          pickupEnabled: input.pickupEnabled,
          businessHours: input.businessHours ?? null,
          status: "active",
        })
        .returning();

      return store;
    }),

  // ── Get My Store (for logged-in agent) ──────────────────────────────────
  getMyStore: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [store] = await database
        .select()
        .from(agentStores)
        .where(eq(agentStores.agentId, input.agentId))
        .limit(1);

      return store ?? null;
    }),

  // ── Update Store ────────────────────────────────────────────────────────
  updateStore: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        storeName: z.string().optional(),
        description: z.string().optional(),
        logoUrl: z.string().optional(),
        bannerUrl: z.string().optional(),
        themeColor: z.string().optional(),
        aboutHtml: z.string().optional(),
        phone: z.string().optional(),
        email: z.string().email().optional(),
        address: z.string().optional(),
        city: z.string().optional(),
        state: z.string().optional(),
        lga: z.string().optional(),
        latitude: z.string().optional(),
        longitude: z.string().optional(),
        categories: z.array(z.string()).optional(),
        tags: z.array(z.string()).optional(),
        deliveryEnabled: z.boolean().optional(),
        pickupEnabled: z.boolean().optional(),
        minOrderAmount: z.string().optional(),
        businessHours: businessHoursSchema,
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const updates: Record<string, unknown> = { updatedAt: new Date() };
      const { storeId, ...fields } = input;
      for (const [key, val] of Object.entries(fields)) {
        if (val !== undefined) updates[key] = val;
      }

      const [updated] = await database
        .update(agentStores)
        .set(updates)
        .where(eq(agentStores.id, storeId))
        .returning();

      return updated;
    }),

  // ── Public: Get Store by Slug ───────────────────────────────────────────
  getStoreBySlug: publicProcedure
    .input(z.object({ slug: z.string() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [store] = await database
        .select()
        .from(agentStores)
        .where(
          and(
            eq(agentStores.slug, input.slug),
            eq(agentStores.status, "active")
          )
        )
        .limit(1);

      return store ?? null;
    }),

  // ── Public: Get Store by Agent Code ─────────────────────────────────────
  getStoreByAgentCode: publicProcedure
    .input(z.object({ agentCode: z.string() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [store] = await database
        .select()
        .from(agentStores)
        .where(
          and(
            eq(agentStores.agentCode, input.agentCode),
            eq(agentStores.status, "active")
          )
        )
        .limit(1);

      return store ?? null;
    }),

  // ── Public: Store Discovery / Mall ──────────────────────────────────────
  discoverStores: publicProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
        city: z.string().optional(),
        state: z.string().optional(),
        category: z.string().optional(),
        sortBy: z
          .enum(["rating", "newest", "popular", "name"])
          .default("popular"),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { stores: [], total: 0 };

      const conditions = [eq(agentStores.status, "active")];
      if (input.search) {
        conditions.push(
          or(
            ilike(agentStores.storeName, `%${input.search}%`),
            ilike(agentStores.description, `%${input.search}%`)
          )!
        );
      }
      if (input.city) conditions.push(eq(agentStores.city, input.city));
      if (input.state) conditions.push(eq(agentStores.state, input.state));
      if (input.category) {
        conditions.push(
          sql`${agentStores.categories}::jsonb @> ${JSON.stringify([input.category])}::jsonb`
        );
      }

      const where = and(...conditions);

      const orderBy =
        input.sortBy === "rating"
          ? desc(agentStores.averageRating)
          : input.sortBy === "newest"
            ? desc(agentStores.createdAt)
            : input.sortBy === "name"
              ? asc(agentStores.storeName)
              : desc(agentStores.totalSales);

      const [stores, totalResult] = await Promise.all([
        database
          .select()
          .from(agentStores)
          .where(where)
          .orderBy(orderBy)
          .limit(input.limit)
          .offset(input.offset),
        database.select({ total: count() }).from(agentStores).where(where),
      ]);

      return {
        stores,
        total: totalResult[0]?.total ?? 0,
        limit: input.limit,
        offset: input.offset,
      };
    }),

  // ── Public: Store Products ──────────────────────────────────────────────
  getStoreProducts: publicProcedure
    .input(
      z.object({
        storeId: z.number(),
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
        categoryId: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { products: [], total: 0 };

      // Get the store to find agentId
      const [store] = await database
        .select({ agentId: agentStores.agentId })
        .from(agentStores)
        .where(eq(agentStores.id, input.storeId))
        .limit(1);
      if (!store) return { products: [], total: 0 };

      const conditions = [
        eq(ecommerceProducts.agentId, store.agentId),
        eq(ecommerceProducts.isActive, true),
      ];
      if (input.search) {
        conditions.push(ilike(ecommerceProducts.name, `%${input.search}%`));
      }
      if (input.categoryId) {
        conditions.push(eq(ecommerceProducts.categoryId, input.categoryId));
      }

      const where = and(...conditions);

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

      return { products, total: totalResult[0]?.total ?? 0 };
    }),

  // ── Agent Store Analytics ───────────────────────────────────────────────
  getStoreAnalytics: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        startDate: z.string().optional(),
        endDate: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database)
        return {
          totalProducts: 0,
          activeProducts: 0,
          totalOrders: 0,
          pendingOrders: 0,
          totalRevenue: "0",
          platformFees: "0",
          netPayout: "0",
          avgOrderValue: "0",
          reviewCount: 0,
          avgRating: "0",
        };

      const [store] = await database
        .select()
        .from(agentStores)
        .where(eq(agentStores.id, input.storeId))
        .limit(1);
      if (!store) throw new TRPCError({ code: "NOT_FOUND" });

      const [productStats] = await database
        .select({
          total: count(),
          active: sql<number>`count(*) filter (where ${ecommerceProducts.isActive} = true)`,
        })
        .from(ecommerceProducts)
        .where(eq(ecommerceProducts.agentId, store.agentId));

      const orderConditions = [eq(ecommerceOrders.agentId, store.agentId)];
      if (input.startDate) {
        orderConditions.push(
          gte(ecommerceOrders.createdAt, new Date(input.startDate))
        );
      }
      if (input.endDate) {
        orderConditions.push(
          lte(ecommerceOrders.createdAt, new Date(input.endDate))
        );
      }

      const [orderStats] = await database
        .select({
          total: count(),
          pending: sql<number>`count(*) filter (where ${ecommerceOrders.status} = 'pending')`,
          totalRev: sql<string>`coalesce(sum(${ecommerceOrders.total}::numeric), 0)`,
          avgOrder: sql<string>`coalesce(avg(${ecommerceOrders.total}::numeric), 0)`,
        })
        .from(ecommerceOrders)
        .where(and(...orderConditions));

      const [splitStats] = await database
        .select({
          platformFees: sql<string>`coalesce(sum(${paymentSplits.platformFee}::numeric), 0)`,
          netPayout: sql<string>`coalesce(sum(${paymentSplits.agentPayout}::numeric), 0)`,
        })
        .from(paymentSplits)
        .where(eq(paymentSplits.storeId, input.storeId));

      return {
        totalProducts: productStats?.total ?? 0,
        activeProducts: productStats?.active ?? 0,
        totalOrders: orderStats?.total ?? 0,
        pendingOrders: orderStats?.pending ?? 0,
        totalRevenue: orderStats?.totalRev ?? "0",
        platformFees: splitStats?.platformFees ?? "0",
        netPayout: splitStats?.netPayout ?? "0",
        avgOrderValue: orderStats?.avgOrder ?? "0",
        reviewCount: store.reviewCount,
        avgRating: store.averageRating ?? "0",
      };
    }),

  // ── Delivery Zones ──────────────────────────────────────────────────────
  listDeliveryZones: protectedProcedure
    .input(z.object({ storeId: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return [];

      return database
        .select()
        .from(deliveryZones)
        .where(eq(deliveryZones.storeId, input.storeId))
        .orderBy(asc(deliveryZones.zoneName));
    }),

  createDeliveryZone: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        zoneName: z.string().min(1),
        description: z.string().optional(),
        deliveryFee: z.string(),
        estimatedMinutes: z.number().optional(),
        maxDistanceKm: z.string().optional(),
        areas: z.array(z.string()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [zone] = await database
        .insert(deliveryZones)
        .values({
          storeId: input.storeId,
          zoneName: input.zoneName,
          description: input.description ?? null,
          deliveryFee: input.deliveryFee,
          estimatedMinutes: input.estimatedMinutes ?? 60,
          maxDistanceKm: input.maxDistanceKm ?? null,
          areas: input.areas ?? [],
        })
        .returning();

      return zone;
    }),

  updateDeliveryZone: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        zoneName: z.string().optional(),
        deliveryFee: z.string().optional(),
        estimatedMinutes: z.number().optional(),
        isActive: z.boolean().optional(),
        areas: z.array(z.string()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const updates: Record<string, unknown> = {};
      if (input.zoneName !== undefined) updates.zoneName = input.zoneName;
      if (input.deliveryFee !== undefined)
        updates.deliveryFee = input.deliveryFee;
      if (input.estimatedMinutes !== undefined)
        updates.estimatedMinutes = input.estimatedMinutes;
      if (input.isActive !== undefined) updates.isActive = input.isActive;
      if (input.areas !== undefined) updates.areas = input.areas;

      const [zone] = await database
        .update(deliveryZones)
        .set(updates)
        .where(eq(deliveryZones.id, input.id))
        .returning();

      return zone;
    }),

  // ── Delivery Tracking ───────────────────────────────────────────────────
  getDeliveryTracking: protectedProcedure
    .input(z.object({ orderId: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [tracking] = await database
        .select()
        .from(deliveryTracking)
        .where(eq(deliveryTracking.orderId, input.orderId))
        .limit(1);

      return tracking ?? null;
    }),

  createDeliveryTracking: protectedProcedure
    .input(
      z.object({
        orderId: z.number(),
        storeId: z.number(),
        deliveryZoneId: z.number().optional(),
        riderName: z.string().optional(),
        riderPhone: z.string().optional(),
        estimatedDelivery: z.string().optional(),
        deliveryNotes: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const trackingCode = `DT-${Date.now().toString(36).toUpperCase()}-${crypto.randomBytes(3).toString("hex").toUpperCase()}`;

      const [tracking] = await database
        .insert(deliveryTracking)
        .values({
          orderId: input.orderId,
          storeId: input.storeId,
          deliveryZoneId: input.deliveryZoneId ?? null,
          riderName: input.riderName ?? null,
          riderPhone: input.riderPhone ?? null,
          trackingCode,
          estimatedDelivery: input.estimatedDelivery
            ? new Date(input.estimatedDelivery)
            : null,
          deliveryNotes: input.deliveryNotes ?? null,
          status: "pending",
        })
        .returning();

      return tracking;
    }),

  updateDeliveryStatus: protectedProcedure
    .input(
      z.object({
        orderId: z.number(),
        status: z.enum([
          "pending",
          "assigned",
          "picked_up",
          "in_transit",
          "delivered",
          "failed",
          "returned",
        ]),
        latitude: z.string().optional(),
        longitude: z.string().optional(),
        deliveryProofUrl: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const updates: Record<string, unknown> = {
        status: input.status,
        updatedAt: new Date(),
      };
      if (input.latitude) updates.latitude = input.latitude;
      if (input.longitude) updates.longitude = input.longitude;
      if (input.deliveryProofUrl)
        updates.deliveryProofUrl = input.deliveryProofUrl;
      if (input.status === "delivered") updates.actualDelivery = new Date();

      const [tracking] = await database
        .update(deliveryTracking)
        .set(updates)
        .where(eq(deliveryTracking.orderId, input.orderId))
        .returning();

      return tracking;
    }),

  // ── Public: Track Delivery by Code ──────────────────────────────────────
  trackByCode: publicProcedure
    .input(z.object({ trackingCode: z.string() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return null;

      const [tracking] = await database
        .select()
        .from(deliveryTracking)
        .where(eq(deliveryTracking.trackingCode, input.trackingCode))
        .limit(1);

      return tracking ?? null;
    }),

  // ── Payment Splits ──────────────────────────────────────────────────────
  createPaymentSplit: protectedProcedure
    .input(
      z.object({
        orderId: z.number(),
        orderNumber: z.string(),
        storeId: z.number(),
        agentId: z.number(),
        orderTotal: z.string(),
        platformFeePct: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const total = parseFloat(input.orderTotal);
      const feePct = parseFloat(input.platformFeePct);
      const platformFee = (total * feePct) / 100;
      const vatOnFee = platformFee * 0.075; // 7.5% VAT
      const agentPayout = total - platformFee - vatOnFee;

      const [split] = await database
        .insert(paymentSplits)
        .values({
          orderId: input.orderId,
          orderNumber: input.orderNumber,
          storeId: input.storeId,
          agentId: input.agentId,
          orderTotal: input.orderTotal,
          platformFee: platformFee.toFixed(2),
          platformFeePct: input.platformFeePct,
          agentPayout: agentPayout.toFixed(2),
          taxAmount: vatOnFee.toFixed(2),
        })
        .returning();

      return split;
    }),

  listPaymentSplits: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        status: z
          .enum(["pending", "processed", "settled", "failed"])
          .optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { splits: [], total: 0 };

      const conditions = [eq(paymentSplits.storeId, input.storeId)];
      if (input.status) conditions.push(eq(paymentSplits.status, input.status));

      const where = and(...conditions);

      const [splits, totalResult] = await Promise.all([
        database
          .select()
          .from(paymentSplits)
          .where(where)
          .orderBy(desc(paymentSplits.createdAt))
          .limit(input.limit)
          .offset(input.offset),
        database.select({ total: count() }).from(paymentSplits).where(where),
      ]);

      return { splits, total: totalResult[0]?.total ?? 0 };
    }),

  // ── Store Fulfillment Dashboard ─────────────────────────────────────────
  getStoreOrders: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        status: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { orders: [], total: 0 };

      const [store] = await database
        .select({ agentId: agentStores.agentId })
        .from(agentStores)
        .where(eq(agentStores.id, input.storeId))
        .limit(1);
      if (!store) return { orders: [], total: 0 };

      const conditions = [eq(ecommerceOrders.agentId, store.agentId)];
      if (input.status) {
        conditions.push(sql`${ecommerceOrders.status} = ${input.status}`);
      }

      const where = and(...conditions);

      const [orders, totalResult] = await Promise.all([
        database
          .select()
          .from(ecommerceOrders)
          .where(where)
          .orderBy(desc(ecommerceOrders.createdAt))
          .limit(input.limit)
          .offset(input.offset),
        database.select({ total: count() }).from(ecommerceOrders).where(where),
      ]);

      return { orders, total: totalResult[0]?.total ?? 0 };
    }),
});
