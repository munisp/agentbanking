import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { auditLog } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";

export const announcementReactionsRouter = router({
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
          .from(auditLog)
          .orderBy(desc((auditLog as any).id))
          .limit(input.limit)
          .offset(input.offset);

        const [totalRow] = await database
          .select({ total: count() })
          .from(auditLog);

        return {
          data: results,
          total: totalRow?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch (error) {
        console.error("[announcementReactions] list error:", error);
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
        .from(auditLog)
        .where(eq((auditLog as any).id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`announcementReactions record #${input.id} not found`);
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
          FROM audit_log`
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
      console.error("[announcementReactions] getStats error:", error);
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
    const [totalRow] = await database.select({ total: count() }).from(auditLog);
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
        .from(auditLog)
        .where(gte((auditLog as any).createdAt, since))
        .orderBy(desc((auditLog as any).id))
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
          FROM audit_log
          WHERE created_at >= now() - make_interval(days => ${input.days})
          GROUP BY date_trunc('day', created_at)
          ORDER BY date`
        );
        return Array.isArray(rows) ? rows : (rows as any).rows ?? [];
      } catch {
        return [];
      }
    }),

  getReactions: protectedProcedure
    .input(z.object({ announcementId: z.union([z.string(), z.number()]) }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { reactions: [], comments: [] };
      try {
        const reactions = await database.execute(
          sql`SELECT action as emoji, count(*) as count, array_agg(distinct user_id) as users
          FROM audit_log
          WHERE details->>'announcement_id' = ${String(input.announcementId)}
          AND action LIKE 'reaction_%'
          GROUP BY action`
        );
        const comments = await database.execute(
          sql`SELECT user_id, details->>'text' as text, created_at
          FROM audit_log
          WHERE details->>'announcement_id' = ${String(input.announcementId)}
          AND action = 'comment'
          ORDER BY created_at DESC
          LIMIT 50`
        );
        return {
          reactions: Array.isArray(reactions) ? reactions : (reactions as any).rows ?? [],
          comments: Array.isArray(comments) ? comments : (comments as any).rows ?? [],
        };
      } catch {
        return { reactions: [], comments: [] };
      }
    }),

  react: protectedProcedure
    .input(z.object({
      announcementId: z.union([z.string(), z.number()]),
      emoji: z.string().min(1).max(10),
    }))
    .mutation(async ({ input, ctx }) => {
      const database = await getDb();
      if (!database) return { success: false };
      const userId = (ctx as any).user?.id ?? "anonymous";
      await database.insert(auditLog).values({
        action: `reaction_${input.emoji}`,
        userId,
        details: { announcement_id: String(input.announcementId), emoji: input.emoji },
      } as any);
      return { success: true };
    }),

  comment: protectedProcedure
    .input(z.object({
      announcementId: z.union([z.string(), z.number()]),
      text: z.string().min(1).max(1000),
    }))
    .mutation(async ({ input, ctx }) => {
      const database = await getDb();
      if (!database) return { success: false };
      const userId = (ctx as any).user?.id ?? "anonymous";
      await database.insert(auditLog).values({
        action: "comment",
        userId,
        details: { announcement_id: String(input.announcementId), text: input.text },
      } as any);
      return { success: true };
    }),
});
