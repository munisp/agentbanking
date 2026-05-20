import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const qdrantVectorSearchRouter = router({
  search: protectedProcedure
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
        .from(auditLog)
        .orderBy(desc(auditLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(auditLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "vector_search",
        procedure: "search",
      };
    }),
  index: protectedProcedure
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
        action: "vector_search.index",
        resource: "vector_search",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "vector_search",
        action: "index",
        id: input?.id || null,
      };
    }),
  collections: protectedProcedure
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
        .from(auditLog)
        .orderBy(desc(auditLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(auditLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "vector_search",
        procedure: "collections",
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
        .from(auditLog)
        .orderBy(desc(auditLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(auditLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "vector_search",
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
        .from(auditLog)
        .orderBy(desc(auditLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(auditLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "vector_search",
        procedure: "config",
      };
    }),
  health: protectedProcedure.query(async () => {
    return {
      status: "healthy",
      uptime: process.uptime(),
      memory: process.memoryUsage().heapUsed,
      timestamp: new Date().toISOString(),
    };
  }),
  analytics: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeItems: 0,
      lastUpdated: new Date().toISOString(),
    };
  }),
  collectionStats: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, id: input?.id ?? null };
    }),
  semanticSearch: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
  ragAnswer: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
});
