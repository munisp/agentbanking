/**
 * CBN Agent Banking Transaction Limits
 * Per Central Bank of Nigeria Guidelines on Agent Banking (2013, revised 2021)
 *
 * Tier 1 (Bronze): Max ₦50,000/transaction, ₦300,000/day
 * Tier 2 (Silver): Max ₦200,000/transaction, ₦1,000,000/day
 * Tier 3 (Gold/Platinum): Max ₦5,000,000/transaction, ₦10,000,000/day
 */
import { sql, eq, and, gte } from "drizzle-orm";
import { transactions } from "../../drizzle/schema";

export const KYC_TIER_LIMITS = {
  Bronze: { single: 50_000, daily: 300_000, monthly: 3_000_000 },
  Silver: { single: 200_000, daily: 1_000_000, monthly: 10_000_000 },
  Gold: { single: 5_000_000, daily: 10_000_000, monthly: 50_000_000 },
  Platinum: { single: 5_000_000, daily: 10_000_000, monthly: 50_000_000 },
} as const;

export interface LimitCheckResult {
  allowed: boolean;
  todayTotal: number;
  dailyLimit: number;
  singleLimit: number;
  remaining: number;
  reason?: string;
}

/**
 * Check if a transaction would exceed the agent's daily cumulative limit.
 * Queries today's successful transactions and validates against tier limits.
 */
export async function checkDailyLimit(
  db: any,
  agentId: number,
  tier: string,
  amount: number
): Promise<LimitCheckResult> {
  const limits =
    KYC_TIER_LIMITS[tier as keyof typeof KYC_TIER_LIMITS] ??
    KYC_TIER_LIMITS.Bronze;

  // Check single transaction limit
  if (amount > limits.single) {
    return {
      allowed: false,
      todayTotal: 0,
      dailyLimit: limits.daily,
      singleLimit: limits.single,
      remaining: 0,
      reason: `Amount ₦${amount.toLocaleString()} exceeds single transaction limit of ₦${limits.single.toLocaleString()} for ${tier} tier`,
    };
  }

  // Get today's cumulative total
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const [result] = await db
    .select({
      total: sql<string>`COALESCE(SUM(CAST(amount AS numeric)), 0)`,
    })
    .from(transactions)
    .where(
      and(
        eq(transactions.agentId, agentId),
        eq(transactions.status, "success"),
        gte(transactions.createdAt, today)
      )
    );

  const todayTotal = Number(result?.total ?? 0);
  const remaining = Math.max(0, limits.daily - todayTotal);

  if (todayTotal + amount > limits.daily) {
    return {
      allowed: false,
      todayTotal,
      dailyLimit: limits.daily,
      singleLimit: limits.single,
      remaining,
      reason: `Daily cumulative limit exceeded. Today: ₦${todayTotal.toLocaleString()}, Limit: ₦${limits.daily.toLocaleString()}`,
    };
  }

  return {
    allowed: true,
    todayTotal,
    dailyLimit: limits.daily,
    singleLimit: limits.single,
    remaining: remaining - amount,
  };
}
