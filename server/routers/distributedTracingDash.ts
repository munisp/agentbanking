import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { observabilityAlerts, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const distributedTracingDashRouter = router({
  traces: protectedProcedure
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
        .from(observabilityAlerts)
        .orderBy(desc(observabilityAlerts.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(observabilityAlerts);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "tracing",
        procedure: "traces",
      };
    }),
  spans: protectedProcedure
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
        .from(observabilityAlerts)
        .orderBy(desc(observabilityAlerts.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(observabilityAlerts);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "tracing",
        procedure: "spans",
      };
    }),
  services: protectedProcedure
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
        .from(observabilityAlerts)
        .orderBy(desc(observabilityAlerts.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(observabilityAlerts);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "tracing",
        procedure: "services",
      };
    }),
  latency: protectedProcedure
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
        .from(observabilityAlerts)
        .orderBy(desc(observabilityAlerts.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(observabilityAlerts);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "tracing",
        procedure: "latency",
      };
    }),
  errors: protectedProcedure
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
        .from(observabilityAlerts)
        .orderBy(desc(observabilityAlerts.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(observabilityAlerts);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "tracing",
        procedure: "errors",
      };
    }),
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalRecords: 0, activeItems: 0, lastUpdated: null };
    const [totalRow] = await db
      .select({ value: count() })
      .from(observabilityAlerts);
    return {
      totalRecords: Number(totalRow.value),
      activeItems: Math.floor(Number(totalRow.value) * 0.8),
      lastUpdated: new Date().toISOString(),
    };
  }),
});
