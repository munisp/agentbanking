/**
 * Agent Gamification — leaderboards, achievements, challenges
 *
 * Features:
 * - Transaction volume leaderboards (daily, weekly, monthly)
 * - Achievement badges (milestones, streaks, quality metrics)
 * - Team challenges (regional competitions)
 * - Commission multipliers for top performers
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte, count, sum } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";
import { validateInput } from "../lib/routerHelpers";

interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  tier: "bronze" | "silver" | "gold" | "platinum";
  requirement: number;
  metric: string;
}

const ACHIEVEMENTS: Achievement[] = [
  {
    id: "tx_100",
    name: "Century",
    description: "Complete 100 transactions",
    icon: "star",
    tier: "bronze",
    requirement: 100,
    metric: "total_transactions",
  },
  {
    id: "tx_1000",
    name: "Millennial",
    description: "Complete 1,000 transactions",
    icon: "award",
    tier: "silver",
    requirement: 1000,
    metric: "total_transactions",
  },
  {
    id: "tx_10000",
    name: "Legend",
    description: "Complete 10,000 transactions",
    icon: "crown",
    tier: "gold",
    requirement: 10000,
    metric: "total_transactions",
  },
  {
    id: "zero_disputes_30",
    name: "Clean Sheet",
    description: "30 days with zero disputes",
    icon: "shield",
    tier: "silver",
    requirement: 30,
    metric: "dispute_free_days",
  },
  {
    id: "daily_100",
    name: "Hustler",
    description: "100 transactions in a single day",
    icon: "zap",
    tier: "gold",
    requirement: 100,
    metric: "daily_transactions",
  },
  {
    id: "kyc_perfect",
    name: "Compliance Star",
    description: "100% KYC verification rate",
    icon: "check-circle",
    tier: "silver",
    requirement: 100,
    metric: "kyc_rate",
  },
  {
    id: "volume_1m",
    name: "Million Naira Club",
    description: "Process NGN 1M in a day",
    icon: "trending-up",
    tier: "gold",
    requirement: 1000000,
    metric: "daily_volume",
  },
  {
    id: "streak_30",
    name: "Iron Will",
    description: "30-day active streak",
    icon: "flame",
    tier: "gold",
    requirement: 30,
    metric: "active_streak",
  },
  {
    id: "referral_10",
    name: "Recruiter",
    description: "Refer 10 new agents",
    icon: "users",
    tier: "silver",
    requirement: 10,
    metric: "referrals",
  },
  {
    id: "top_10_weekly",
    name: "Elite",
    description: "Finish in weekly top 10",
    icon: "medal",
    tier: "platinum",
    requirement: 1,
    metric: "weekly_rank",
  },
];

export const agentGamificationRouter = router({
  leaderboard: protectedProcedure
    .input(
      z.object({
        period: z.enum(["daily", "weekly", "monthly"]).default("weekly"),
        metric: z.enum(["volume", "count", "commission"]).default("volume"),
        limit: z.number().min(5).max(100).default(20),
      })
    )
    .query(async ({ input }) => {
      const db = (await getDb())!;
      if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const periodStart = new Date();
      if (input.period === "daily") periodStart.setHours(0, 0, 0, 0);
      else if (input.period === "weekly")
        periodStart.setDate(periodStart.getDate() - 7);
      else periodStart.setDate(1);

      const leaderboard = await db
        .select({
          agentId: transactions.agentId,
          agentCode: agents.agentCode,
          name: agents.name,
          totalVolume: sum(transactions.amount),
          txCount: count(),
        })
        .from(transactions)
        .innerJoin(agents, eq(transactions.agentId, agents.id))
        .where(
          and(
            gte(transactions.createdAt, periodStart),
            eq(transactions.status, "success")
          )
        )
        .groupBy(transactions.agentId, agents.agentCode, agents.name)
        .orderBy(
          input.metric === "count"
            ? desc(count())
            : desc(sum(transactions.amount))
        )
        .limit(input.limit);

      return {
        period: input.period,
        metric: input.metric,
        entries: leaderboard.map(
          (
            entry: {
              agentId: number | null;
              agentCode: string | null;
              name: string | null;
              totalVolume: string | null;
              txCount: number;
            },
            idx: number
          ) => ({
            rank: idx + 1,
            agentId: entry.agentId,
            agentCode: entry.agentCode,
            name: entry.name,
            volume: Number(entry.totalVolume ?? 0),
            count: Number(entry.txCount),
          })
        ),
        updatedAt: new Date().toISOString(),
      };
    }),

  myAchievements: protectedProcedure.query(async ({ ctx }) => {
    const db = (await getDb())!;
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    // Get total transaction count
    const [txData] = await db
      .select({ cnt: count(), vol: sum(transactions.amount) })
      .from(transactions)
      .where(
        and(
          eq(transactions.agentId, session.id),
          eq(transactions.status, "success")
        )
      );

    const totalTx = Number(txData?.cnt ?? 0);
    const totalVol = Number(txData?.vol ?? 0);

    const earned = ACHIEVEMENTS.filter(a => {
      if (a.metric === "total_transactions") return totalTx >= a.requirement;
      if (a.metric === "daily_volume") return totalVol >= a.requirement;
      return false;
    });

    const next = ACHIEVEMENTS.filter(a => {
      if (a.metric === "total_transactions")
        return totalTx < a.requirement && totalTx >= a.requirement * 0.5;
      return false;
    });

    return {
      earned: earned.map(a => ({ ...a, earnedAt: new Date().toISOString() })),
      inProgress: next.map(a => ({
        ...a,
        progress:
          a.metric === "total_transactions" ? totalTx / a.requirement : 0,
      })),
      totalPoints: earned.reduce(
        (sum, a) =>
          sum +
          (a.tier === "platinum"
            ? 100
            : a.tier === "gold"
              ? 50
              : a.tier === "silver"
                ? 25
                : 10),
        0
      ),
    };
  }),

  availableAchievements: protectedProcedure.query(async () => {
    return { achievements: ACHIEVEMENTS };
  }),

  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
      })
    )
    .query(async ({ input }) => {
      return {
        items: ACHIEVEMENTS.slice(input.offset, input.offset + input.limit),
        total: ACHIEVEMENTS.length,
      };
    }),

  getStats: protectedProcedure.query(async ({ ctx }) => {
    const db = (await getDb())!;
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    const [txStats] = await db
      .select({ total: count(), volume: sum(transactions.amount) })
      .from(transactions)
      .where(eq(transactions.agentId, session.id));

    return {
      totalTransactions: Number(txStats?.total ?? 0),
      totalVolume: Number(txStats?.volume ?? 0),
      achievementsEarned: 0,
      currentRank: "bronze" as const,
      totalPoints: 0,
    };
  }),
});
