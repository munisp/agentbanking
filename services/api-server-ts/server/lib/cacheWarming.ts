/**
 * Cache warming — preloads hot data into Redis on server startup.
 *
 * Warms:
 *  - System config / feature flags
 *  - Exchange rates (refreshed every 15 min)
 *  - Commission rate rules
 *  - Platform settings
 *
 * All warming is fail-open — server starts regardless of Redis availability.
 */

import { cacheSet } from "../redisClient";
import { getDb } from "../db";
import {
  platformSettings,
  systemConfig,
  commissionRules,
} from "../../drizzle/schema";
import { desc } from "drizzle-orm";

interface WarmResult {
  key: string;
  success: boolean;
  count: number;
  durationMs: number;
}

async function warmSystemConfig(): Promise<WarmResult> {
  const start = Date.now();
  try {
    const db = await getDb();
    if (!db)
      return { key: "system:config", success: false, count: 0, durationMs: 0 };
    const rows = await db.select().from(systemConfig).limit(100);
    for (const row of rows) {
      await cacheSet(`config:${row.key}`, JSON.stringify(row), 3600);
    }
    return {
      key: "system:config",
      success: true,
      count: rows.length,
      durationMs: Date.now() - start,
    };
  } catch {
    return {
      key: "system:config",
      success: false,
      count: 0,
      durationMs: Date.now() - start,
    };
  }
}

async function warmPlatformSettings(): Promise<WarmResult> {
  const start = Date.now();
  try {
    const db = await getDb();
    if (!db)
      return {
        key: "platform:settings",
        success: false,
        count: 0,
        durationMs: 0,
      };
    const rows = await db.select().from(platformSettings).limit(200);
    await cacheSet("platform:settings:all", JSON.stringify(rows), 1800);
    return {
      key: "platform:settings",
      success: true,
      count: rows.length,
      durationMs: Date.now() - start,
    };
  } catch {
    return {
      key: "platform:settings",
      success: false,
      count: 0,
      durationMs: Date.now() - start,
    };
  }
}

async function warmCommissionRules(): Promise<WarmResult> {
  const start = Date.now();
  try {
    const db = await getDb();
    if (!db)
      return {
        key: "commission:rules",
        success: false,
        count: 0,
        durationMs: 0,
      };
    const rows = await db
      .select()
      .from(commissionRules)
      .orderBy(desc(commissionRules.id))
      .limit(100);
    for (const rule of rows) {
      await cacheSet(`commission:rule:${rule.id}`, JSON.stringify(rule), 1800);
    }
    await cacheSet("commission:rules:all", JSON.stringify(rows), 1800);
    return {
      key: "commission:rules",
      success: true,
      count: rows.length,
      durationMs: Date.now() - start,
    };
  } catch {
    return {
      key: "commission:rules",
      success: false,
      count: 0,
      durationMs: Date.now() - start,
    };
  }
}

export async function warmCaches(): Promise<WarmResult[]> {
  console.log("[CacheWarming] Starting cache warm-up...");
  const results = await Promise.allSettled([
    warmSystemConfig(),
    warmPlatformSettings(),
    warmCommissionRules(),
  ]);

  const outcomes: WarmResult[] = results.map(r =>
    r.status === "fulfilled"
      ? r.value
      : { key: "unknown", success: false, count: 0, durationMs: 0 }
  );

  const totalKeys = outcomes.reduce((s, o) => s + o.count, 0);
  const totalMs = outcomes.reduce((s, o) => s + o.durationMs, 0);
  const failed = outcomes.filter(o => !o.success).length;

  console.log(
    `[CacheWarming] Done — ${totalKeys} keys warmed in ${totalMs}ms (${failed} failures)`
  );
  return outcomes;
}
