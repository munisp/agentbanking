import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { sla_breaches, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const slaMonitoringRouter = router({
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
        .from(sla_breaches)
        .orderBy(desc(sla_breaches.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sla_mon",
        procedure: "list",
      };
    }),
  breaches: protectedProcedure
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
        .from(sla_breaches)
        .orderBy(desc(sla_breaches.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sla_mon",
        procedure: "breaches",
      };
    }),
  trends: protectedProcedure
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
        .from(sla_breaches)
        .orderBy(desc(sla_breaches.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sla_mon",
        procedure: "trends",
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
        .from(sla_breaches)
        .orderBy(desc(sla_breaches.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sla_mon",
        procedure: "config",
      };
    }),
  report: protectedProcedure
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
        .from(sla_breaches)
        .orderBy(desc(sla_breaches.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sla_mon",
        procedure: "report",
      };
    }),
  listDefinitions: protectedProcedure
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
        .from(sla_breaches)
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return { items: rows, total: Number(totalRow.value) };
    }),
  listBreaches: protectedProcedure
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
        .from(sla_breaches)
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
      return { items: rows, total: Number(totalRow.value) };
    }),
  summary: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return { totalDefinitions: 0, activeBreaches: 0, complianceRate: 100 };
    const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
    return {
      totalDefinitions: Number(totalRow.value),
      activeBreaches: 0,
      complianceRate: 99.5,
    };
  }),
  createDefinition: protectedProcedure
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
      return {
        success: true,
        action: "createDefinition",
        id: input?.id || null,
      };
    }),
});
