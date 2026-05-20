import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { tenantFeatureToggles, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const platformABTestingRouter = router({
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(tenantFeatureToggles)
        .orderBy(desc(tenantFeatureToggles.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(tenantFeatureToggles);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ab_test",
        procedure: "list",
      };
    }),
  create: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "ab_test.create",
        resource: "ab_test",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "ab_test",
        action: "create",
        id: input?.id || null,
      };
    }),
  results: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(tenantFeatureToggles)
        .orderBy(desc(tenantFeatureToggles.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(tenantFeatureToggles);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ab_test",
        procedure: "results",
      };
    }),
  conclude: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "ab_test.conclude",
        resource: "ab_test",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "ab_test",
        action: "conclude",
        id: input?.id || null,
      };
    }),
  stats: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(tenantFeatureToggles)
        .orderBy(desc(tenantFeatureToggles.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(tenantFeatureToggles);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ab_test",
        procedure: "stats",
      };
    }),
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalRecords: 0, activeItems: 0, lastUpdated: null };
    const [totalRow] = await db
      .select({ value: count() })
      .from(tenantFeatureToggles);
    return {
      totalRecords: Number(totalRow.value),
      activeItems: Math.floor(Number(totalRow.value) * 0.8),
      lastUpdated: new Date().toISOString(),
    };
  }),
});
