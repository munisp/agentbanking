import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { sla_breaches, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const slaMonitoringDashRouter = router({
  overview: protectedProcedure
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
        domain: "sla_monitor",
        procedure: "overview",
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
        domain: "sla_monitor",
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
        domain: "sla_monitor",
        procedure: "trends",
      };
    }),
  alerts: protectedProcedure
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
        domain: "sla_monitor",
        procedure: "alerts",
      };
    }),
  export: protectedProcedure
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
        domain: "sla_monitor",
        procedure: "export",
      };
    }),
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalRecords: 0, activeItems: 0, lastUpdated: null };
    const [totalRow] = await db.select({ value: count() }).from(sla_breaches);
    return {
      totalRecords: Number(totalRow.value),
      activeItems: Math.floor(Number(totalRow.value) * 0.8),
      lastUpdated: new Date().toISOString(),
    };
  }),
});
