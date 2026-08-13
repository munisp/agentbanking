/**
 * fxRateFeed.ts — live FX rate feed backed by the Frankfurter API
 * (https://api.frankfurter.dev), which publishes ECB reference rates.
 *
 * Design:
 *  - Rates are fetched over HTTP with a hard timeout — no fabricated data.
 *  - Snapshots are cached in Redis and persisted in the system_config table
 *    together with a `fetchedAt` timestamp.
 *  - Callers must resolve rates via `getFreshFxSnapshot` / `getLivePairRate`.
 *    If no snapshot younger than the staleness window exists and the live
 *    fetch fails, a TRPCError(SERVICE_UNAVAILABLE) is thrown — we never
 *    fall back to hardcoded rate tables or silent 1:1 conversions.
 *  - Note: the ECB feed does not cover every currency (e.g. NGN, GHS, XOF
 *    are not ECB reference currencies). `pairRateFromSnapshot` returns null
 *    for uncovered currencies and callers must fail loud.
 */
import { TRPCError } from "@trpc/server";
import { eq } from "drizzle-orm";
import { getDb } from "../db";
import { systemConfig } from "../../drizzle/schema";

const FRANKFURTER_URL = "https://api.frankfurter.dev/v1";
const FETCH_TIMEOUT_MS = 5_000;
const SNAPSHOT_CONFIG_KEY = "fx_live_snapshot";
const SNAPSHOT_CACHE_KEY = "fx:live:snapshot";

/** Default freshness window for cached snapshots (6 hours). */
export const FX_SNAPSHOT_MAX_AGE_MS = 6 * 60 * 60 * 1000;

export interface FxSnapshot {
  /** Base currency of the snapshot (ECB reference rates are EUR-based). */
  base: string;
  /** Units of currency X per 1 unit of `base` (Frankfurter-native shape). */
  rates: Record<string, number>;
  fetchedAt: string;
  source: "frankfurter/ecb";
}

async function fetchJson(url: string): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`Frankfurter API ${url} → HTTP ${res.status}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

/** Fetch the latest rates directly from Frankfurter (no cache). Throws on failure. */
export async function fetchFrankfurterSnapshot(): Promise<FxSnapshot> {
  const data = await fetchJson(`${FRANKFURTER_URL}/latest`);
  if (!data || typeof data.rates !== "object" || data.rates === null) {
    throw new Error("Frankfurter API returned a malformed payload");
  }
  const rates: Record<string, number> = {};
  for (const [ccy, value] of Object.entries(data.rates)) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 0) rates[ccy] = n;
  }
  if (Object.keys(rates).length === 0) {
    throw new Error("Frankfurter API returned zero usable rates");
  }
  return {
    base: typeof data.base === "string" ? data.base : "EUR",
    rates,
    fetchedAt: new Date().toISOString(),
    source: "frankfurter/ecb",
  };
}

/** Fetch a historical timeseries directly from Frankfurter. Throws on failure. */
export async function fetchFrankfurterTimeseries(
  base: string,
  target: string,
  days: number
): Promise<{ date: string; rate: number }[]> {
  const clamped = Math.min(Math.max(Math.floor(days), 1), 365);
  const end = new Date();
  const start = new Date(end.getTime() - clamped * 86_400_000);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const data = await fetchJson(
    `${FRANKFURTER_URL}/${fmt(start)}..${fmt(end)}?from=${encodeURIComponent(base)}&to=${encodeURIComponent(target)}`
  );
  if (!data || typeof data.rates !== "object" || data.rates === null) {
    throw new Error("Frankfurter API returned a malformed timeseries payload");
  }
  const series = Object.entries(
    data.rates as Record<string, Record<string, number>>
  )
    .map(([date, perDay]) => ({ date, rate: Number(perDay?.[target]) }))
    .filter(p => Number.isFinite(p.rate))
    .sort((a, b) => a.date.localeCompare(b.date));
  if (series.length === 0) {
    throw new Error(
      `Frankfurter API returned no observations for ${base}/${target}`
    );
  }
  return series;
}

async function readCachedSnapshot(): Promise<FxSnapshot | null> {
  try {
    const { cacheGet } = await import("../redisClient");
    const raw = await cacheGet(SNAPSHOT_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(String(raw)) as FxSnapshot;
    return parsed && parsed.rates ? parsed : null;
  } catch {
    return null;
  }
}

async function readStoredSnapshot(): Promise<FxSnapshot | null> {
  try {
    const db = await getDb();
    if (!db) return null;
    const rows = await db
      .select()
      .from(systemConfig)
      .where(eq(systemConfig.key, SNAPSHOT_CONFIG_KEY))
      .limit(1);
    if (!rows[0]) return null;
    const parsed = JSON.parse(String(rows[0].value)) as FxSnapshot;
    return parsed && parsed.rates ? parsed : null;
  } catch {
    return null;
  }
}

/** Persist a snapshot to system_config (authoritative) + Redis (best-effort). */
export async function persistFxSnapshot(snapshot: FxSnapshot): Promise<void> {
  const db = await getDb();
  if (!db) {
    throw new Error("Database unavailable — cannot persist FX snapshot");
  }
  await db
    .insert(systemConfig)
    .values({ key: SNAPSHOT_CONFIG_KEY, value: JSON.stringify(snapshot) })
    .onConflictDoUpdate({
      target: systemConfig.key,
      set: { value: JSON.stringify(snapshot), updatedAt: new Date() },
    });
  try {
    const { cacheSet } = await import("../redisClient");
    await cacheSet(
      SNAPSHOT_CACHE_KEY,
      JSON.stringify(snapshot),
      Math.floor(FX_SNAPSHOT_MAX_AGE_MS / 1000)
    );
  } catch {
    /* cache write is best-effort; the DB row above is authoritative */
  }
}

function isFresh(snapshot: FxSnapshot, maxAgeMs: number): boolean {
  const ts = Date.parse(snapshot.fetchedAt);
  return Number.isFinite(ts) && Date.now() - ts <= maxAgeMs;
}

/**
 * Return a snapshot no older than `maxAgeMs`.
 * Resolution order: Redis → system_config → live Frankfurter fetch (persisted).
 * Throws TRPCError(SERVICE_UNAVAILABLE) when no fresh data exists and the
 * live feed cannot be reached — never fabricates rates.
 */
export async function getFreshFxSnapshot(
  maxAgeMs: number = FX_SNAPSHOT_MAX_AGE_MS
): Promise<FxSnapshot> {
  const cached = await readCachedSnapshot();
  if (cached && isFresh(cached, maxAgeMs)) return cached;

  const stored = await readStoredSnapshot();
  if (stored && isFresh(stored, maxAgeMs)) return stored;

  try {
    const fresh = await fetchFrankfurterSnapshot();
    await persistFxSnapshot(fresh);
    return fresh;
  } catch (err) {
    const staleNote = stored
      ? ` Cached snapshot is stale (fetched at ${stored.fetchedAt}).`
      : " No cached snapshot exists.";
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Live FX rates unavailable from the Frankfurter/ECB feed: ${err instanceof Error ? err.message : "unknown error"}.${staleNote}`,
    });
  }
}

/**
 * Compute the rate for a currency pair from a snapshot.
 * Returns units of `to` per 1 unit of `from`, or null when either currency
 * is not covered by the feed (callers must fail loud — never invent a rate).
 */
export function pairRateFromSnapshot(
  snapshot: FxSnapshot,
  from: string,
  to: string
): number | null {
  if (from === to) return 1;
  const perBase = (ccy: string): number | undefined =>
    ccy === snapshot.base ? 1 : snapshot.rates[ccy];
  const fromPerBase = perBase(from);
  const toPerBase = perBase(to);
  if (
    typeof fromPerBase !== "number" ||
    typeof toPerBase !== "number" ||
    !(fromPerBase > 0) ||
    !(toPerBase > 0)
  ) {
    return null;
  }
  return toPerBase / fromPerBase;
}

/**
 * Resolve a live pair rate with a staleness guard.
 * Throws TRPCError(SERVICE_UNAVAILABLE) when no fresh rate exists.
 */
export async function getLivePairRate(
  from: string,
  to: string,
  maxAgeMs: number = FX_SNAPSHOT_MAX_AGE_MS
): Promise<{ rate: number; fetchedAt: string; source: string }> {
  const snapshot = await getFreshFxSnapshot(maxAgeMs);
  const rate = pairRateFromSnapshot(snapshot, from, to);
  if (rate === null) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `No live FX rate available for ${from}/${to}: currency not covered by the Frankfurter/ECB feed (snapshot base ${snapshot.base}, fetched at ${snapshot.fetchedAt}).`,
    });
  }
  return { rate, fetchedAt: snapshot.fetchedAt, source: snapshot.source };
}
