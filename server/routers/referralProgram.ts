import { z } from "zod";
import { publicProcedure, protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { users } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";

export const referralProgramRouter = router({
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(users)
        .where(eq(users.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const [totalResult] = await database.select({ total: count() }).from(users);

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
        .from(users)
        .orderBy(desc(users.id))
        .limit(input.limit);

      return results;
    }),

  list: publicProcedure.query(async () => {
    return {
      referrals: [
        {
          id: "RF-001",
          referrerId: "AGT-001",
          referredId: "AGT-005",
          status: "active",
          reward: 5000,
          createdAt: "2024-06-01",
        },
      ],
      total: 1,
    };
  }),
  tiers: publicProcedure.query(async () => {
    return {
      tiers: [
        { name: "Starter", minReferrals: 0, reward: 2000 },
        { name: "Champion", minReferrals: 10, reward: 5000 },
        { name: "Ambassador", minReferrals: 50, reward: 10000 },
      ],
    };
  }),
  leaderboard: publicProcedure.query(async () => {
    return {
      leaderboard: [
        {
          agentId: "AGT-001",
          name: "Adebayo",
          totalReferrals: 25,
          totalRewards: 125000,
          rank: 1,
        },
      ],
    };
  }),
  analytics: publicProcedure.query(async () => {
    return {
      totalReferrals: 500,
      qualified: 400,
      totalBonusPaid: 2500000,
      conversionRate: 80,
    };
  }),
});
