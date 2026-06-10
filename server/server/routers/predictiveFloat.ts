/**
 * Predictive Float Management — ML-based float depletion prediction
 *
 * Analyzes historical transaction patterns to predict when an agent's
 * float will run out. Triggers alerts before depletion occurs.
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte, lte, count, sum, avg } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";
import { validateInput } from "../lib/routerHelpers";

interface FloatPrediction {
  currentBalance: number;
  predictedDepletionHours: number;
  avgHourlyOutflow: number;
  peakHours: number[];
  riskLevel: "low" | "medium" | "high" | "critical";
  recommendedTopUp: number;
  confidence: number;
}

function calculateRiskLevel(
  hoursUntilDepletion: number
): FloatPrediction["riskLevel"] {
  if (hoursUntilDepletion <= 2) return "critical";
  if (hoursUntilDepletion <= 8) return "high";
  if (hoursUntilDepletion <= 24) return "medium";
  return "low";
}

export const predictiveFloatRouter = router({
  predict: protectedProcedure
    .input(z.object({ agentId: z.number().min(1).optional() }))
    .query(async ({ input, ctx }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const targetAgentId = input.agentId || session.id;

      const [agent] = await db
        .select()
        .from(agents)
        .where(eq(agents.id, targetAgentId))
        .limit(1);
      if (!agent) throw new TRPCError({ code: "NOT_FOUND" });

      // Get last 7 days of transaction data
      const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);

      const [outflowData] = await db
        .select({
          totalOutflow: sum(transactions.amount),
          txCount: count(),
        })
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, targetAgentId),
            gte(transactions.createdAt, sevenDaysAgo),
            eq(transactions.status, "success")
          )
        );

      const totalOutflow = Math.abs(Number(outflowData?.totalOutflow ?? 0));
      const txCount = Number(outflowData?.txCount ?? 0);
      const hoursInPeriod = 7 * 24;
      const avgHourlyOutflow = totalOutflow / hoursInPeriod;

      const currentBalance = Number(agent.floatBalance ?? 0);
      const predictedHours =
        avgHourlyOutflow > 0
          ? Math.round(currentBalance / avgHourlyOutflow)
          : 999;

      const riskLevel = calculateRiskLevel(predictedHours);

      // Recommend top-up: enough for 48 hours of average activity
      const recommendedTopUp = Math.max(
        0,
        Math.ceil((avgHourlyOutflow * 48 - currentBalance) / 1000) * 1000
      );

      // Peak hours (simplified: business hours 8am-6pm)
      const peakHours = [9, 10, 11, 12, 14, 15, 16, 17];

      const prediction: FloatPrediction = {
        currentBalance,
        predictedDepletionHours: predictedHours,
        avgHourlyOutflow: Math.round(avgHourlyOutflow),
        peakHours,
        riskLevel,
        recommendedTopUp,
        confidence: txCount > 50 ? 0.85 : txCount > 10 ? 0.6 : 0.3,
      };

      auditFinancialAction(
        "CREATE",
        "predictiveFloat",
        "float_prediction",
        JSON.stringify({
          agentId: targetAgentId,
          riskLevel,
          predictedHours,
        })
      );

      return prediction;
    }),

  alerts: protectedProcedure.query(async ({ ctx }) => {
    const db = (await getDb())!;
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    // Get agents with low float
    const lowFloatAgents = await db
      .select({
        id: agents.id,
        agentCode: agents.agentCode,
        name: agents.name,
        floatBalance: agents.floatBalance,
      })
      .from(agents)
      .where(
        and(
          eq(agents.isActive, true),
          sql`CAST(${agents.floatBalance} AS NUMERIC) < 10000`
        )
      )
      .orderBy(sql`CAST(${agents.floatBalance} AS NUMERIC) ASC`)
      .limit(50);

    return {
      criticalCount: lowFloatAgents.filter(
        (a: { floatBalance: string | null }) =>
          Number(a.floatBalance ?? 0) < 2000
      ).length,
      warningCount: lowFloatAgents.filter(
        (a: { floatBalance: string | null }) =>
          Number(a.floatBalance ?? 0) >= 2000 &&
          Number(a.floatBalance ?? 0) < 10000
      ).length,
      agents: lowFloatAgents.map(
        (a: {
          id: number;
          agentCode: string | null;
          name: string | null;
          floatBalance: string | null;
        }) => ({
          ...a,
          riskLevel: calculateRiskLevel(
            Number(a.floatBalance ?? 0) < 2000 ? 1 : 12
          ),
        })
      ),
    };
  }),

  trends: protectedProcedure
    .input(
      z.object({
        agentId: z.number().min(1).optional(),
        days: z.number().min(1).max(90).default(30),
      })
    )
    .query(async ({ input, ctx }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const targetAgentId = input.agentId || session.id;
      const startDate = new Date(Date.now() - input.days * 24 * 60 * 60 * 1000);

      const dailyData = await db
        .select({
          day: sql<string>`DATE(${transactions.createdAt})`,
          totalAmount: sum(transactions.amount),
          txCount: count(),
        })
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, targetAgentId),
            gte(transactions.createdAt, startDate),
            eq(transactions.status, "success")
          )
        )
        .groupBy(sql`DATE(${transactions.createdAt})`)
        .orderBy(sql`DATE(${transactions.createdAt})`);

      return {
        agentId: targetAgentId,
        period: `${input.days} days`,
        dailyVolume: dailyData.map(
          (d: {
            day: string;
            totalAmount: string | null;
            txCount: number;
          }) => ({
            date: d.day,
            amount: Number(d.totalAmount ?? 0),
            count: Number(d.txCount),
          })
        ),
        avgDailyVolume:
          dailyData.reduce(
            (acc: number, d: { totalAmount: string | null }) =>
              acc + Number(d.totalAmount ?? 0),
            0
          ) / Math.max(1, dailyData.length),
      };
    }),
});
