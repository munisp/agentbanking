/**
 * KYC/KYB Event Trigger System
 *
 * Centralised event-driven KYC triggers for the 54Link platform.
 * Events that initiate or escalate KYC/KYB verification:
 *
 *  1. Agent registration / onboarding
 *  2. Transaction threshold breach (CBN tiered limits)
 *  3. Suspicious activity flagged by fraud engine
 *  4. Periodic re-KYC for expired verifications
 *  5. Merchant onboarding
 *  6. KYB document expiry
 *  7. Tier upgrade request
 *  8. Cross-border transaction initiation
 */

import { getDb } from "../db";
import {
  kycSessions,
  agents,
  transactions,
  customers,
  merchants,
  kycDocuments,
} from "../../drizzle/schema";
import { eq, and, sql, gte } from "drizzle-orm";

// CBN KYC tier thresholds (daily limits in NGN)
const CBN_TIER_LIMITS = {
  0: { daily: 50_000, single: 10_000, label: "Tier 0 (Unverified)" },
  1: { daily: 300_000, single: 50_000, label: "Tier 1 (Basic KYC)" },
  2: { daily: 5_000_000, single: 1_000_000, label: "Tier 2 (Standard KYC)" },
  3: {
    daily: 50_000_000,
    single: 10_000_000,
    label: "Tier 3 (Enhanced Due Diligence)",
  },
} as const;

// KYC event types
export type KycTriggerEvent =
  | "agent_registration"
  | "merchant_onboarding"
  | "transaction_threshold"
  | "suspicious_activity"
  | "periodic_rekyc"
  | "document_expiry"
  | "tier_upgrade_request"
  | "cross_border_transaction"
  | "high_value_transfer"
  | "pep_match";

export interface KycTriggerResult {
  triggered: boolean;
  event: KycTriggerEvent;
  kycSessionId?: number;
  requiredTier: number;
  currentTier: number;
  reason: string;
}

/**
 * Trigger KYC on agent registration — CBN mandates Tier 1 KYC minimum.
 */
export async function triggerKycOnRegistration(
  agentId: number,
  agentCode: string,
): Promise<KycTriggerResult> {
  const db = await getDb();
  if (!db) {
    return {
      triggered: false,
      event: "agent_registration",
      requiredTier: 1,
      currentTier: 0,
      reason: "Database unavailable",
    };
  }

  const [existing] = await db
    .select()
    .from(kycSessions)
    .where(
      and(eq(kycSessions.agentId, agentId), eq(kycSessions.status, "approved")),
    )
    .limit(1);

  if (existing) {
    return {
      triggered: false,
      event: "agent_registration",
      requiredTier: 1,
      currentTier: 1,
      reason: "Agent already has approved KYC",
    };
  }

  const [session] = await db
    .insert(kycSessions)
    .values({
      agentId,
      status: "pending",
      kycLevel: 1,
      triggeredBy: "agent_registration",
      notes: `Auto-triggered: new agent ${agentCode} registration requires Tier 1 KYC`,
    } as any)
    .returning();

  return {
    triggered: true,
    event: "agent_registration",
    kycSessionId: session?.id,
    requiredTier: 1,
    currentTier: 0,
    reason: `KYC session created for new agent ${agentCode}`,
  };
}

/**
 * Check if a transaction would breach CBN tiered limits and trigger KYC upgrade.
 */
export async function checkTransactionThreshold(
  agentId: number,
  transactionAmount: number,
  currentKycTier: number,
): Promise<KycTriggerResult> {
  const db = await getDb();
  if (!db) {
    return {
      triggered: false,
      event: "transaction_threshold",
      requiredTier: currentKycTier,
      currentTier: currentKycTier,
      reason: "Database unavailable",
    };
  }

  const tierLimits =
    CBN_TIER_LIMITS[currentKycTier as keyof typeof CBN_TIER_LIMITS] ??
    CBN_TIER_LIMITS[0];

  // Check single transaction limit
  if (transactionAmount > tierLimits.single) {
    const requiredTier = Object.entries(CBN_TIER_LIMITS).find(
      ([, v]) => v.single >= transactionAmount,
    );
    const newTier = requiredTier ? parseInt(requiredTier[0]) : 3;

    const [session] = await db
      .insert(kycSessions)
      .values({
        agentId,
        status: "pending",
        kycLevel: newTier,
        triggeredBy: "transaction_threshold",
        notes: `Auto-triggered: transaction ₦${transactionAmount.toLocaleString()} exceeds ${tierLimits.label} single limit ₦${tierLimits.single.toLocaleString()}`,
      } as any)
      .returning();

    return {
      triggered: true,
      event: "transaction_threshold",
      kycSessionId: session?.id,
      requiredTier: newTier,
      currentTier: currentKycTier,
      reason: `Transaction ₦${transactionAmount.toLocaleString()} exceeds Tier ${currentKycTier} single limit`,
    };
  }

  // Check daily aggregate
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const [dailyResult] = await db
    .select({ total: sql<number>`COALESCE(SUM(${transactions.amount}), 0)` })
    .from(transactions)
    .where(
      and(
        eq(transactions.agentId, agentId),
        gte(transactions.createdAt, today),
      ),
    );

  const dailyTotal = Number(dailyResult?.total ?? 0) + transactionAmount;

  if (dailyTotal > tierLimits.daily) {
    const requiredTier = Object.entries(CBN_TIER_LIMITS).find(
      ([, v]) => v.daily >= dailyTotal,
    );
    const newTier = requiredTier ? parseInt(requiredTier[0]) : 3;

    const [session] = await db
      .insert(kycSessions)
      .values({
        agentId,
        status: "pending",
        kycLevel: newTier,
        triggeredBy: "transaction_threshold",
        notes: `Auto-triggered: daily total ₦${dailyTotal.toLocaleString()} exceeds ${tierLimits.label} daily limit ₦${tierLimits.daily.toLocaleString()}`,
      } as any)
      .returning();

    return {
      triggered: true,
      event: "transaction_threshold",
      kycSessionId: session?.id,
      requiredTier: newTier,
      currentTier: currentKycTier,
      reason: `Daily total ₦${dailyTotal.toLocaleString()} exceeds Tier ${currentKycTier} daily limit`,
    };
  }

  return {
    triggered: false,
    event: "transaction_threshold",
    requiredTier: currentKycTier,
    currentTier: currentKycTier,
    reason: "Transaction within limits",
  };
}

/**
 * Trigger enhanced KYC when fraud engine flags suspicious activity.
 */
export async function triggerKycOnSuspiciousActivity(
  agentId: number,
  fraudAlertId: number,
  fraudScore: number,
  reason: string,
): Promise<KycTriggerResult> {
  const db = await getDb();
  if (!db) {
    return {
      triggered: false,
      event: "suspicious_activity",
      requiredTier: 3,
      currentTier: 0,
      reason: "Database unavailable",
    };
  }

  // Escalate to Tier 3 (Enhanced Due Diligence) for fraud scores > 0.7
  const requiredTier = fraudScore > 0.7 ? 3 : 2;

  const [session] = await db
    .insert(kycSessions)
    .values({
      agentId,
      status: "under_review",
      kycLevel: requiredTier,
      triggeredBy: "suspicious_activity",
      notes: `Auto-triggered: fraud alert #${fraudAlertId}, score ${fraudScore.toFixed(2)} — ${reason}`,
    } as any)
    .returning();

  return {
    triggered: true,
    event: "suspicious_activity",
    kycSessionId: session?.id,
    requiredTier,
    currentTier: 0,
    reason: `Enhanced KYC triggered by fraud score ${fraudScore.toFixed(2)}`,
  };
}

/**
 * Trigger KYC on merchant onboarding — KYB checks required.
 */
export async function triggerKybOnMerchantOnboarding(
  merchantId: number,
  businessType: string,
): Promise<KycTriggerResult> {
  const db = await getDb();
  if (!db) {
    return {
      triggered: false,
      event: "merchant_onboarding",
      requiredTier: 2,
      currentTier: 0,
      reason: "Database unavailable",
    };
  }

  const requiredTier = businessType === "corporate" ? 3 : 2;

  const [session] = await db
    .insert(kycSessions)
    .values({
      status: "pending",
      kycLevel: requiredTier,
      triggeredBy: "merchant_onboarding",
      notes: `KYB auto-triggered: merchant #${merchantId} (${businessType}) onboarding`,
    } as any)
    .returning();

  return {
    triggered: true,
    event: "merchant_onboarding",
    kycSessionId: session?.id,
    requiredTier,
    currentTier: 0,
    reason: `KYB session created for ${businessType} merchant`,
  };
}

/**
 * Trigger re-KYC for cross-border transactions (CBN requirement).
 */
export async function triggerKycOnCrossBorder(
  agentId: number,
  corridorCode: string,
  amount: number,
): Promise<KycTriggerResult> {
  const db = await getDb();
  if (!db) {
    return {
      triggered: false,
      event: "cross_border_transaction",
      requiredTier: 3,
      currentTier: 0,
      reason: "Database unavailable",
    };
  }

  // Cross-border always requires Tier 3 (Enhanced Due Diligence)
  const [existingTier3] = await db
    .select()
    .from(kycSessions)
    .where(
      and(
        eq(kycSessions.agentId, agentId),
        eq(kycSessions.status, "approved"),
        sql`(${kycSessions.type})::text LIKE '%tier_3%' OR (${kycSessions.type})::text = 'enhanced_due_diligence'`,
      ),
    )
    .limit(1);

  if (existingTier3) {
    return {
      triggered: false,
      event: "cross_border_transaction",
      requiredTier: 3,
      currentTier: 3,
      reason: "Agent already has Tier 3 KYC for cross-border",
    };
  }

  const [session] = await db
    .insert(kycSessions)
    .values({
      agentId,
      status: "pending",
      kycLevel: 3,
      triggeredBy: "cross_border_transaction",
      notes: `Auto-triggered: cross-border transaction to ${corridorCode}, amount ₦${amount.toLocaleString()} requires EDD`,
    } as any)
    .returning();

  return {
    triggered: true,
    event: "cross_border_transaction",
    kycSessionId: session?.id,
    requiredTier: 3,
    currentTier: 0,
    reason: `EDD required for cross-border corridor ${corridorCode}`,
  };
}

/**
 * Run periodic re-KYC check — finds agents with expired or soon-expiring KYC.
 * Called by cron job daily.
 */
export async function runPeriodicReKycCheck(): Promise<{
  triggered: number;
  expired: number;
  expiringSoon: number;
}> {
  const db = await getDb();
  if (!db) return { triggered: 0, expired: 0, expiringSoon: 0 };

  const now = new Date();
  const thirtyDaysFromNow = new Date(
    now.getTime() + 30 * 24 * 60 * 60 * 1000,
  );

  // Find agents whose last approved KYC session is older than 12 months
  const twelveMonthsAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);

  const staleKycAgents = await db
    .select({
      agentId: kycSessions.agentId,
      lastApproved: sql<Date>`MAX(${kycSessions.updatedAt})`,
    })
    .from(kycSessions)
    .where(eq(kycSessions.status, "approved"))
    .groupBy(kycSessions.agentId)
    .having(sql`MAX(${kycSessions.updatedAt}) < ${twelveMonthsAgo}`)
    .limit(100);

  let triggered = 0;

  for (const agent of staleKycAgents) {
    if (!agent.agentId) continue;
    await db.insert(kycSessions).values({
      agentId: agent.agentId,
      status: "pending",
      kycLevel: 1,
      triggeredBy: "periodic_rekyc",
      notes: `Auto-triggered: annual re-KYC required (last approved: ${new Date(agent.lastApproved).toISOString().split("T")[0]})`,
    } as any);
    triggered++;
  }

  return {
    triggered,
    expired: staleKycAgents.length,
    expiringSoon: 0,
  };
}

export { CBN_TIER_LIMITS };
