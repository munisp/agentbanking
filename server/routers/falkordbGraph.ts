import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { auditLog, platform_health_checks } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

export const falkordbGraphRouter = router({
  query: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "falkordb",
        procedure: "query",
      };
    }),
  schema: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "falkordb",
        procedure: "schema",
      };
    }),
  nodes: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "falkordb",
        procedure: "nodes",
      };
    }),
  edges: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "falkordb",
        procedure: "edges",
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "falkordb",
        procedure: "stats",
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
  getNeighbors: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, id: input?.id ?? null };
    }),
  shortestPath: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, id: input?.id ?? null };
    }),
  fraudRings: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, id: input?.id ?? null };
    }),
});
