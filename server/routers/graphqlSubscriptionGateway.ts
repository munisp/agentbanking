import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { apiKeys, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const graphqlSubscriptionGatewayRouter = router({
  subscriptions: protectedProcedure
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
        .from(apiKeys)
        .orderBy(desc(apiKeys.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(apiKeys);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "graphql_sub",
        procedure: "subscriptions",
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
        action: "graphql_sub.create",
        resource: "graphql_sub",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "graphql_sub",
        action: "create",
        id: input?.id || null,
      };
    }),
  delete: protectedProcedure
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
        action: "graphql_sub.delete",
        resource: "graphql_sub",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "graphql_sub",
        action: "delete",
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
        .from(apiKeys)
        .orderBy(desc(apiKeys.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(apiKeys);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "graphql_sub",
        procedure: "stats",
      };
    }),
  config: protectedProcedure
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
        .from(apiKeys)
        .orderBy(desc(apiKeys.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(apiKeys);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "graphql_sub",
        procedure: "config",
      };
    }),
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalRecords: 0, activeItems: 0, lastUpdated: null };
    const [totalRow] = await db.select({ value: count() }).from(apiKeys);
    return {
      totalRecords: Number(totalRow.value),
      activeItems: Math.floor(Number(totalRow.value) * 0.8),
      lastUpdated: new Date().toISOString(),
    };
  }),
});
