import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { observabilityAlerts, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const openTelemetryRouter = router({
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
        domain: "otel",
        procedure: "traces",
      };
    }),
  metrics: protectedProcedure
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
        domain: "otel",
        procedure: "metrics",
      };
    }),
  logs: protectedProcedure
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
        domain: "otel",
        procedure: "logs",
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
        domain: "otel",
        procedure: "alerts",
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
        domain: "otel",
        procedure: "config",
      };
    }),
});
