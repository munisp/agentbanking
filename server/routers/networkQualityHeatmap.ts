import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { connectivityLog, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const networkQualityHeatmapRouter = router({
  heatmap: protectedProcedure
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "network_quality",
        procedure: "heatmap",
      };
    }),
  regions: protectedProcedure
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "network_quality",
        procedure: "regions",
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "network_quality",
        procedure: "alerts",
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "network_quality",
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "network_quality",
        procedure: "config",
      };
    }),
});
