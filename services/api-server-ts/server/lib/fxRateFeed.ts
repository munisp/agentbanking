/**
 * fxRateFeed — live FX rate feed with DB-backed cache and staleness guard.
 *
 * Replaces hardcoded / simulated FX rate tables. Rates are fetched from
 * public FX APIs with a fetch timeout:
 *   - Frankfurter (https://api.frankfurter.app) — ECB reference rates
 *   - open.er-api.com — covers NGN and other non-ECB African currencies
 *
 * Fetched rates are cached in the system_config table together with a
 * fetched-at timestamp. Callers only receive rates while they are fresh;
 * when no fresh rate can be obtained a TRPCError(SERVICE_UNAVAILABLE) is
 * thrown so money-moving paths fail loud instead of quoting stale or
 * fabricated rates.
 */
import { eq } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getDb } from "../db";
import { systemConfig } from "../../drizzle/schema";

const FETCH_TIMEOUT_MS = 8_000;
/** Rates older than this are considered stale and must be refreshed. */
const STALE_AFTER_MS = 6 * 60 * 60 * 1000; // 6 hours
const CACHE_KEY_PREFIX = "fx_rates_live:";
const SPREADS_KEY = "fx_spreads";

/** Bases refreshed by the fxRates.refresh mutation. */
export const DEFAULT_RATE_BASES = ["NGN", "USD"];

/** ECB / Frankfurter reference currencies. */
const ECB_CURRENCIES = new Set([
  "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
  "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR",
  "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD",
  "ZAR",
]);

export interface RateSet {
  base: string;
  rates: Record<string, number>;
  fetchedAt: string;
  source: string;
}

async function fetchJson(url: string): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

function sanitizeRates(raw: unknown): Record<string, number> {
  const out: Record<string, number> = {};
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      const n = Number(v);
      if (Number.isFinite(n) && n > 0) out[k.toUpperCase()] = n;
    }
  }
  return out;
}

/**
 * Fetch the latest rates for `base` from public FX APIs (with timeout).
 * Throws SERVICE_UNAVAILABLE when no live source can serve the base.
 */
export async function fetchLiveRates(
  base: string
): Promise<{ base: string; rates: Record<string, number>; source: string }> {
  const b = base.toUpperCase();
  // Primary: Frankfurter / ECB reference rates (ECB currencies only)
  if (ECB_CURRENCIES.has(b)) {
    try {
      const data = await fetchJson(
        `https://api.frankfurter.app/latest?from=${encodeURIComponent(b)}`
      );
      const rates = sanitizeRates(data?.rates);
      if (Object.keys(rates).length > 0) {
        return { base: b, rates, source: "frankfurter/ecb" };
      }
    } catch {
      // fall through to the secondary public provider
    }
  }
  // Secondary: open.er-api.com (covers NGN, GHS, KES, XOF, XAF, TZS, ...)
  const data = await fetchJson(
    `https://open.er-api.com/v6/latest/${encodeURIComponent(b)}`
  );
  if (data && data.result === "success") {
    const rates = sanitizeRates(data.rates);
    if (Object.keys(rates).length > 0) {
      return { base: b, rates, source: "open.er-api.com" };
    }
  }
  throw new TRPCError({
    code: "SERVICE_UNAVAILABLE",
    message: `No live FX rate source available for base currency ${b}`,
  });
}

async function readCache(base: string): Promise<RateSet | null> {
  try {
    const db = await getDb();
    if (!db) return null;
    const [row] = await db
      .select()
      .from(systemConfig)
      .where(eq(systemConfig.key, CACHE_KEY_PREFIX + base))
      .limit(1);
    if (!row) return null;
    const parsed = JSON.parse(String(row.value));
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !parsed.rates ||
      !parsed.fetchedAt
    )
      return null;
    return {
      base,
      rates: sanitizeRates(parsed.rates),
      fetchedAt: String(parsed.fetchedAt),
      source: String(parsed.source ?? "unknown"),
    };
  } catch {
    return null;
  }
}

async function writeCache(
  base: string,
  rates: Record<string, number>,
  source: string
): Promise<RateSet> {
  const db = await getDb();
  if (!db)
    throw new TRPCError({
      code: "INTERNAL_SERVER_ERROR",
      message: "Database unavailable — cannot persist FX rate cache",
    });
  const payload: RateSet = {
    base,
    rates,
    fetchedAt: new Date().toISOString(),
    source,
  };
  const value = JSON.stringify(payload);
  await db
    .insert(systemConfig)
    .values({ key: CACHE_KEY_PREFIX + base, value })
    .onConflictDoUpdate({
      target: systemConfig.key,
      set: { value, updatedAt: new Date() },
    });
  return payload;
}

function isFresh(rs: RateSet): boolean {
  const t = new Date(rs.fetchedAt).getTime();
  return Number.isFinite(t) && Date.now() - t < STALE_AFTER_MS;
}

/**
 * Get fresh rates for `base`: serve the DB cache while it is fresh,
 * otherwise refetch from the live feed and persist. Throws
 * SERVICE_UNAVAILABLE when no fresh rate can be obtained — never falls
 * back to stale or hardcoded rates.
 */
export async function getFreshRates(base: string): Promise<RateSet> {
  const b = base.toUpperCase();
  const cached = await readCache(b);
  if (cached && isFresh(cached)) return cached;
  try {
    const live = await fetchLiveRates(b);
    return await writeCache(b, live.rates, live.source);
  } catch (err) {
    if (err instanceof TRPCError) throw err;
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: cached
        ? `FX rates for ${b} are stale (fetched at ${cached.fetchedAt}) and live refresh failed: ${err instanceof Error ? err.message : "unknown"}`
        : `Live FX rates unavailable for ${b}: ${err instanceof Error ? err.message : "unknown"}`,
    });
  }
}

export interface LiveRate {
  from: string;
  to: string;
  rate: number;
  source: string;
  fetchedAt: string;
}

/**
 * Resolve a single live conversion rate (units of `to` per 1 `from`).
 * Throws BAD_REQUEST for unsupported currencies and SERVICE_UNAVAILABLE
 * when no fresh rate exists.
 */
export async function getLiveRate(from: string, to: string): Promise<LiveRate> {
  const f = from.toUpperCase();
  const t = to.toUpperCase();
  if (f === t) {
    return {
      from: f,
      to: t,
      rate: 1,
      source: "identity",
      fetchedAt: new Date().toISOString(),
    };
  }
  const rs = await getFreshRates(f);
  const direct = rs.rates[t];
  if (typeof direct === "number" && direct > 0) {
    return { from: f, to: t, rate: direct, source: rs.source, fetchedAt: rs.fetchedAt };
  }
  // Cross-rate via USD when the direct pair is not quoted
  if (f !== "USD" && t !== "USD") {
    const fToUsd = rs.rates["USD"];
    if (typeof fToUsd === "number" && fToUsd > 0) {
      const usdSet = await getFreshRates("USD");
      const usdToT = usdSet.rates[t];
      if (typeof usdToT === "number" && usdToT > 0) {
        return {
          from: f,
          to: t,
          rate: fToUsd * usdToT,
          source: `${rs.source}+${usdSet.source} (USD cross)`,
          fetchedAt: rs.fetchedAt,
        };
      }
    }
  }
  throw new TRPCError({
    code: "BAD_REQUEST",
    message: `Unsupported currency pair: ${f}-${t}`,
  });
}

/** Read persisted per-pair spreads (percent) from system_config. */
export async function getSpreads(): Promise<Record<string, number>> {
  try {
    const db = await getDb();
    if (!db) return {};
    const [row] = await db
      .select()
      .from(systemConfig)
      .where(eq(systemConfig.key, SPREADS_KEY))
      .limit(1);
    if (!row) return {};
    const parsed = JSON.parse(String(row.value));
    const out: Record<string, number> = {};
    if (parsed && typeof parsed === "object") {
      for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
        const n = Number(v);
        if (Number.isFinite(n) && n >= 0) out[k.toUpperCase()] = n;
      }
    }
    return out;
  } catch {
    return {};
  }
}

/** Persist a spread (percent) for a currency pair. Throws on DB failure. */
export async function saveSpread(
  pair: string,
  spreadPct: number
): Promise<Record<string, number>> {
  if (!Number.isFinite(spreadPct) || spreadPct < 0) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: "Spread must be a non-negative number (percent)",
    });
  }
  const db = await getDb();
  if (!db)
    throw new TRPCError({
      code: "INTERNAL_SERVER_ERROR",
      message: "Database unavailable — cannot persist FX spread",
    });
  const spreads = await getSpreads();
  spreads[pair.toUpperCase()] = spreadPct;
  const value = JSON.stringify(spreads);
  await db
    .insert(systemConfig)
    .values({ key: SPREADS_KEY, value })
    .onConflictDoUpdate({
      target: systemConfig.key,
      set: { value, updatedAt: new Date() },
    });
  return spreads;
}

export function applySpread(rate: number, spreadPct: number): number {
  return rate * (1 + spreadPct / 100);
}

/** Persist a manual (admin) rate override into the live cache. */
export async function saveManualRates(
  base: string,
  rates: Record<string, number>
): Promise<RateSet> {
  const clean = sanitizeRates(rates);
  if (Object.keys(clean).length === 0) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: "No valid rates provided",
    });
  }
  return writeCache(base.toUpperCase(), clean, "manual-override");
}

/**
 * Fetch a real historical time series from the Frankfurter / ECB feed.
 * Throws SERVICE_UNAVAILABLE for non-ECB pairs or feed failures — never
 * synthesizes data.
 */
export async function fetchHistoricalRates(
  base: string,
  target: string,
  days: number
): Promise<{ date: string; rate: number }[]> {
  const b = base.toUpperCase();
  const t = target.toUpperCase();
  const d = Math.min(Math.max(Math.floor(days) || 30, 1), 365);
  if (b === t) {
    const out: { date: string; rate: number }[] = [];
    for (let i = d; i >= 0; i--) {
      out.push({
        date: new Date(Date.now() - i * 86400000).toISOString().slice(0, 10),
        rate: 1,
      });
    }
    return out;
  }
  if (!ECB_CURRENCIES.has(b) || !ECB_CURRENCIES.has(t)) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Historical rates for ${b}/${t} are not published by the ECB/Frankfurter feed`,
    });
  }
  const end = new Date();
  const start = new Date(Date.now() - d * 86400000);
  const fmt = (x: Date) => x.toISOString().slice(0, 10);
  let data: any;
  try {
    data = await fetchJson(
      `https://api.frankfurter.app/${fmt(start)}..${fmt(end)}?from=${encodeURIComponent(b)}&to=${encodeURIComponent(t)}`
    );
  } catch (err) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Frankfurter/ECB historical rate fetch failed: ${err instanceof Error ? err.message : "unknown"}`,
    });
  }
  const raw = data?.rates;
  if (!raw || typeof raw !== "object") {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: "Malformed response from Frankfurter/ECB historical feed",
    });
  }
  const series = Object.keys(raw as Record<string, unknown>)
    .sort()
    .map(date => ({ date, rate: Number((raw as any)[date]?.[t]) }))
    .filter(r => Number.isFinite(r.rate) && r.rate > 0);
  if (series.length === 0) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `No historical data returned for ${b}/${t}`,
    });
  }
  return series;
}

/**
 * Refresh and persist live rates for the given bases. Fails loud
 * (SERVICE_UNAVAILABLE) when nothing could be refreshed — never returns
 * success with zero rates updated.
 */
export async function refreshRates(
  bases: string[]
): Promise<{ refreshedAt: string; ratesUpdated: number; errors?: string[] }> {
  const errors: string[] = [];
  let ratesUpdated = 0;
  for (const base of bases) {
    try {
      const live = await fetchLiveRates(base);
      await writeCache(base.toUpperCase(), live.rates, live.source);
      ratesUpdated++;
    } catch (err) {
      errors.push(
        `${base.toUpperCase()}: ${err instanceof Error ? err.message : "unknown"}`
      );
    }
  }
  if (ratesUpdated === 0) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `FX rate refresh failed for all bases — ${errors.join("; ")}`,
    });
  }
  return {
    refreshedAt: new Date().toISOString(),
    ratesUpdated,
    ...(errors.length > 0 ? { errors } : {}),
  };
}
