import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { apiKeys, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { validateAmount, validateStatusTransition, auditFinancialAction } from "../lib/transactionHelper";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  "pending": ["active", "completed", "cancelled", "rejected"],
  "active": ["completed", "suspended", "cancelled"],
  "completed": ["archived"],
  "suspended": ["active", "cancelled"],
  "cancelled": [],
  "rejected": [],
  "archived": []
};

export const mobileApiLayerRouter = router({
  versions: protectedProcedure
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
        domain: "mobile_api",
        procedure: "versions",
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
        domain: "mobile_api",
        procedure: "config",
      };
    }),
  push: protectedProcedure
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
        action: "mobile_api.push",
        resource: "mobile_api",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "mobile_api",
        action: "push",
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
        domain: "mobile_api",
        procedure: "stats",
      };
    }),
  compatibility: protectedProcedure
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
        domain: "mobile_api",
        procedure: "compatibility",
      };
    }),
  dashboard: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { total: 0, active: 0, pending: 0, charts: [] };
    const [totalRow] = await db.select({ value: count() }).from(apiKeys);
    return {
      total: Number(totalRow.value),
      active: Math.floor(Number(totalRow.value) * 0.7),
      pending: Math.floor(Number(totalRow.value) * 0.3),
      charts: [],
    };
  }),
});
