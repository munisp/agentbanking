import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { observabilityAlerts, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const aiMonitoringRouter = router({
  models: protectedProcedure
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
        domain: "ai_monitor",
        procedure: "models",
      };
    }),
  drift: protectedProcedure
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
        domain: "ai_monitor",
        procedure: "drift",
      };
    }),
  performance: protectedProcedure
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
        domain: "ai_monitor",
        procedure: "performance",
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
        domain: "ai_monitor",
        procedure: "alerts",
      };
    }),
  retrain: protectedProcedure
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
        action: "ai_monitor.retrain",
        resource: "ai_monitor",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "ai_monitor",
        action: "retrain",
        id: input?.id || null,
      };
    }),
  dashboard: protectedProcedure.query(async () => {
    return {
      total: 0,
      active: 0,
      pending: 0,
      lastUpdated: new Date().toISOString(),
    };
  }),
  liveFraudFeed: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
  driftAnalysis: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
  serviceHealth: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
  throughputTimeSeries: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
  acknowledgeAlert: protectedProcedure
    .input(z.object({ id: z.string().optional() }).optional())
    .mutation(async ({ input }) => {
      return {
        success: true,
        action: "acknowledgeAlert",
        id: input?.id ?? null,
        timestamp: new Date().toISOString(),
      };
    }),
});
