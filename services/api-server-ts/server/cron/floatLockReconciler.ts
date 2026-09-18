// @ts-nocheck
import { getDb } from "../db";
import { agents } from "../../drizzle/schema";
import { eq } from "drizzle-orm";
import { cacheGet, cacheIncr } from "../redisClient";

/**
 * Float-lock reconciler — runs every 5 minutes.
 *
 * settlementCron.ts (FF-15) sets DB `agents.floatLocked = true` while an agent
 * is settled, backed by an expiring Redis advisory lock key
 * (`settlement:floatlock:<agentId>`, TTL 1800s). If the process is SIGKILLed
 * mid-run the finally-block unlock never executes: the Redis key expires on
 * its own but the DB flag stays stuck, and transactions.create then rejects
 * ALL transactions for that agent forever.
 *
 * This sweep clears `floatLocked = true` exactly when the corresponding Redis
 * lock key is absent/expired. If Redis itself is unavailable (cacheGet cannot
 * distinguish "key absent" from "Redis down"), the sweep skips the run
 * entirely rather than clearing locks that may still be legitimately held.
 */
export async function runFloatLockReconciler() {
  console.log("[Cron] Running float-lock reconciler...");
  const db = await getDb();
  if (!db) {
    console.warn("[Cron] No DB — skipping float-lock reconciliation");
    return { reconciled: 0 };
  }

  try {
    // Probe Redis availability first: cacheIncr returns 0 on error (same
    // convention as settlementCron lockAgent). Never reconcile blind.
    const probe = await cacheIncr("settlement:floatlock:reconciler_probe", 60);
    if (probe === 0) {
      console.warn(
        "[Cron] Redis unavailable — skipping float-lock reconciliation (locks may be legitimately held)"
      );
      return { reconciled: 0, skipped: "redis_unavailable" };
    }

    const lockedAgents = await db
      .select({ id: agents.id, agentCode: agents.agentCode })
      .from(agents)
      .where(eq(agents.floatLocked, true))
      .limit(500);

    let reconciled = 0;
    for (const agent of lockedAgents) {
      const lockValue = await cacheGet(`settlement:floatlock:${agent.id}`);
      if (lockValue !== null) continue; // lock key still live — leave it alone
      await db
        .update(agents)
        .set({ floatLocked: false, updatedAt: new Date() })
        .where(eq(agents.id, agent.id));
      reconciled++;
      console.log(
        `[Cron] Cleared stuck floatLocked for agent ${agent.agentCode} (Redis lock key absent/expired)`
      );
    }

    console.log(
      `[Cron] Float-lock reconciliation complete: ${reconciled}/${lockedAgents.length} cleared`
    );
    return { reconciled, checked: lockedAgents.length };
  } catch (err) {
    console.error("[Cron] Float-lock reconciler error:", (err as Error).message);
    return { reconciled: 0, error: (err as Error).message };
  }
}
