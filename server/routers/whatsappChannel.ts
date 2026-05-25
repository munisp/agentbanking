import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { notification_logs } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";

export const whatsappChannelRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().optional(),
        status: z.string().optional(),
        startDate: z.string().optional(),
        endDate: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: input.limit, offset: input.offset };

        const results = await database
          .select()
          .from(notification_logs)
          .orderBy(desc((notification_logs as any).id))
          .limit(input.limit)
          .offset(input.offset);

        const [totalRow] = await database
          .select({ total: count() })
          .from(notification_logs);

        return {
          data: results,
          total: totalRow?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch (error) {
        console.error("[whatsappChannel] list error:", error);
        return { data: [], total: 0, limit: input.limit, offset: input.offset };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new Error("Database unavailable");
      const [record] = await database
        .select()
        .from(notification_logs)
        .where(eq((notification_logs as any).id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`whatsappChannel record #${input.id} not found`);
      }
      return record;
    }),

  getStats: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return {
        total: 0,
        active: 0,
        recent: 0,
        growth: 0,
        lastUpdated: new Date().toISOString(),
      };
    try {
      const [stats] = await database.execute(
        sql`SELECT
          count(*) as total,
          count(*) FILTER (WHERE created_at >= now() - interval '30 days') as recent,
          count(*) FILTER (WHERE created_at >= now() - interval '7 days') as this_week,
          count(*) FILTER (WHERE created_at >= now() - interval '1 day') as today
          FROM notification_logs`
      );
      const s = stats as Record<string, unknown>;
      const total = Number(s?.total ?? 0);
      const recent = Number(s?.recent ?? 0);
      const thisWeek = Number(s?.this_week ?? 0);
      const today = Number(s?.today ?? 0);
      const growthRate = total > 0 ? ((recent / Math.max(total - recent, 1)) * 100) : 0;
      return {
        total,
        active: total,
        recent,
        thisWeek,
        today,
        growth: Math.round(growthRate * 100) / 100,
        lastUpdated: new Date().toISOString(),
      };
    } catch (error) {
      console.error("[whatsappChannel] getStats error:", error);
      return {
        total: 0,
        active: 0,
        recent: 0,
        thisWeek: 0,
        today: 0,
        growth: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { totalRecords: 0, lastUpdated: new Date().toISOString() };
    const [totalRow] = await database.select({ total: count() }).from(notification_logs);
    return {
      totalRecords: totalRow?.total ?? 0,
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
      if (!database) return [];
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(notification_logs)
        .where(gte((notification_logs as any).createdAt, since))
        .orderBy(desc((notification_logs as any).id))
        .limit(input.limit);

      return results;
    }),

  getTrend: protectedProcedure
    .input(z.object({ days: z.number().min(1).max(365).default(30) }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return [];
      try {
        const rows = await database.execute(
          sql`SELECT
            date_trunc('day', created_at) as date,
            count(*) as count
          FROM notification_logs
          WHERE created_at >= now() - make_interval(days => ${input.days})
          GROUP BY date_trunc('day', created_at)
          ORDER BY date`
        );
        return Array.isArray(rows) ? rows : (rows as any).rows ?? [];
      } catch {
        return [];
      }
    }),


    templates: protectedProcedure.query(async () => {
    return {
      templates: [
        {
          id: "WT-001",
          name: "Welcome Message",
          category: "transactional",
          status: "approved",
          language: "en",
        },
      ],
      total: 1,
    };
  }),


    messages: protectedProcedure.query(async () => {
    return {
      messages: [
        {
          id: "WM-001",
          templateId: "WT-001",
          recipient: "+2348012345678",
          status: "delivered",
          sentAt: "2024-06-01",
        },
      ],
      total: 1,
    };
  }),
});
