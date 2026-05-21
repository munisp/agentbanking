import { z } from "zod";
import { protectedProcedure, publicProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import {
  productReviews,
  storeReviews,
  agentStores,
} from "../../drizzle/schema";
import { desc, eq, and, count, sql, avg } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

export const storeReviewsRouter = router({
  // ── Product Reviews ─────────────────────────────────────────────────────
  getProductReviews: publicProcedure
    .input(
      z.object({
        productId: z.number(),
        limit: z.number().min(1).max(50).default(10),
        offset: z.number().min(0).default(0),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { reviews: [], total: 0, avgRating: 0 };

      const where = eq(productReviews.productId, input.productId);

      const [reviews, totalResult, ratingResult] = await Promise.all([
        database
          .select()
          .from(productReviews)
          .where(where)
          .orderBy(desc(productReviews.createdAt))
          .limit(input.limit)
          .offset(input.offset),
        database.select({ total: count() }).from(productReviews).where(where),
        database
          .select({ avg: avg(productReviews.rating) })
          .from(productReviews)
          .where(where),
      ]);

      return {
        reviews,
        total: totalResult[0]?.total ?? 0,
        avgRating: ratingResult[0]?.avg ? parseFloat(String(ratingResult[0].avg)) : 0,
      };
    }),

  createProductReview: protectedProcedure
    .input(
      z.object({
        productId: z.number(),
        storeId: z.number(),
        customerId: z.number(),
        customerName: z.string().optional(),
        rating: z.number().min(1).max(5),
        title: z.string().optional(),
        body: z.string().optional(),
        isVerifiedPurchase: z.boolean().default(false),
        images: z.array(z.string()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database)
        throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Database unavailable" });

      // Check for existing review by same customer on same product
      const [existing] = await database
        .select({ id: productReviews.id })
        .from(productReviews)
        .where(
          and(
            eq(productReviews.productId, input.productId),
            eq(productReviews.customerId, input.customerId)
          )
        )
        .limit(1);
      if (existing) {
        throw new TRPCError({ code: "CONFLICT", message: "Already reviewed this product" });
      }

      const [review] = await database
        .insert(productReviews)
        .values({
          productId: input.productId,
          storeId: input.storeId,
          customerId: input.customerId,
          customerName: input.customerName ?? null,
          rating: input.rating,
          title: input.title ?? null,
          body: input.body ?? null,
          isVerifiedPurchase: input.isVerifiedPurchase,
          images: input.images ?? [],
        })
        .returning();

      // Update store average rating
      const [ratingStats] = await database
        .select({
          avgR: avg(productReviews.rating),
          cnt: count(),
        })
        .from(productReviews)
        .where(eq(productReviews.storeId, input.storeId));

      if (ratingStats) {
        await database
          .update(agentStores)
          .set({
            averageRating: ratingStats.avgR ? parseFloat(String(ratingStats.avgR)).toFixed(2) : "0",
            reviewCount: ratingStats.cnt,
            updatedAt: new Date(),
          })
          .where(eq(agentStores.id, input.storeId));
      }

      return review;
    }),

  // ── Seller Reply to Review ──────────────────────────────────────────────
  replyToProductReview: protectedProcedure
    .input(
      z.object({
        reviewId: z.number(),
        reply: z.string().min(1),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [updated] = await database
        .update(productReviews)
        .set({
          sellerReply: input.reply,
          sellerRepliedAt: new Date(),
          updatedAt: new Date(),
        })
        .where(eq(productReviews.id, input.reviewId))
        .returning();

      return updated;
    }),

  markHelpful: protectedProcedure
    .input(z.object({ reviewId: z.number() }))
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [updated] = await database
        .update(productReviews)
        .set({
          helpfulCount: sql`${productReviews.helpfulCount} + 1`,
        })
        .where(eq(productReviews.id, input.reviewId))
        .returning();

      return updated;
    }),

  // ── Store Reviews ───────────────────────────────────────────────────────
  getStoreReviews: publicProcedure
    .input(
      z.object({
        storeId: z.number(),
        limit: z.number().min(1).max(50).default(10),
        offset: z.number().min(0).default(0),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { reviews: [], total: 0, avgRating: 0 };

      const where = eq(storeReviews.storeId, input.storeId);

      const [reviews, totalResult, ratingResult] = await Promise.all([
        database
          .select()
          .from(storeReviews)
          .where(where)
          .orderBy(desc(storeReviews.createdAt))
          .limit(input.limit)
          .offset(input.offset),
        database.select({ total: count() }).from(storeReviews).where(where),
        database
          .select({ avg: avg(storeReviews.rating) })
          .from(storeReviews)
          .where(where),
      ]);

      return {
        reviews,
        total: totalResult[0]?.total ?? 0,
        avgRating: ratingResult[0]?.avg ? parseFloat(String(ratingResult[0].avg)) : 0,
      };
    }),

  createStoreReview: protectedProcedure
    .input(
      z.object({
        storeId: z.number(),
        customerId: z.number(),
        customerName: z.string().optional(),
        rating: z.number().min(1).max(5),
        body: z.string().optional(),
        orderId: z.number().optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [review] = await database
        .insert(storeReviews)
        .values({
          storeId: input.storeId,
          customerId: input.customerId,
          customerName: input.customerName ?? null,
          rating: input.rating,
          body: input.body ?? null,
          orderId: input.orderId ?? null,
        })
        .returning();

      // Update store average rating
      const [stats] = await database
        .select({ avg: avg(storeReviews.rating), cnt: count() })
        .from(storeReviews)
        .where(eq(storeReviews.storeId, input.storeId));

      if (stats) {
        await database
          .update(agentStores)
          .set({
            averageRating: stats.avg ? parseFloat(String(stats.avg)).toFixed(2) : "0",
            reviewCount: stats.cnt,
            updatedAt: new Date(),
          })
          .where(eq(agentStores.id, input.storeId));
      }

      return review;
    }),
});
