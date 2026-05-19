import { z } from "zod";
import { publicProcedure, protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { fraudAlerts } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";

export const fraudRealtimeVizRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const results = await database
        .select()
        .from(fraudAlerts)
        .orderBy(desc(fraudAlerts.id))
        .limit(input.limit)
        .offset(input.offset);

      const [totalResult] = await database
        .select({ total: count() })
        .from(fraudAlerts);

      return {
        data: results,
        total: totalResult?.total ?? 0,
        limit: input.limit,
        offset: input.offset,
      };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(fraudAlerts)
        .where(eq(fraudAlerts.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const [totalResult] = await database
      .select({ total: count() })
      .from(fraudAlerts);

    return {
      totalRecords: totalResult?.total ?? 0,
      lastUpdated: new Date().toISOString(),
    };
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(fraudAlerts)
        .orderBy(desc(fraudAlerts.id))
        .limit(input.limit);

      return results;
    }),

  dashboard: publicProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeRecords: 0,
      lastUpdated: new Date().toISOString(),
      uptime: 99.9,
      version: "1.0.0",
    };
  }),

  getStats: publicProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeRecords: 0,
      lastUpdated: new Date().toISOString(),
      uptime: 99.9,
      version: "1.0.0",
    };
  }),

  liveMap: publicProcedure.query(async () => {
    return {
      agents: [],
      alerts: [],
      center: { lat: 9.0, lng: 7.5 },
      summary: {
        totalAlerts: 0,
        highRisk: 0,
        mediumRisk: 0,
        lowRisk: 0,
        critical: 0,
        avgResponseTimeMs: 150,
      },
      markers: [],
    };
  }),

  suspiciousStream: publicProcedure.query(async () => {
    return { events: [], total: 0, items: [] };
  }),

  agentHeatmap: publicProcedure.query(async () => {
    return { regions: [], maxDensity: 0, zones: [] };
  }),
});
