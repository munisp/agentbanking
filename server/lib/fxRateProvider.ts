/**
 * fxRateProvider.ts — Live FX reference rates via the Frankfurter public API
 * (European Central Bank euro foreign-exchange reference rates).
 *
 * Guarantees:
 *  - Real HTTP fetch with a hard timeout (no fabricated rate tables).
 *  - In-memory cache stamped with the actual fetch time (`fetchedAt`).
 *  - Staleness guard: snapshots older than MAX_STALENESS_MS are never used
 *    for quotes or money movement — callers get SERVICE_UNAVAILABLE instead.
 *  - Unsupported currencies throw NOT_IMPLEMENTED — never a silent 1:1 rate.
 */
import { TRPCError } from "@trpc/server";

const FRANKFURTER_LATEST_URL = "https://api.frankfurter.app/latest";
const FETCH_TIMEOUT_MS = 5_000;
/** Serve from memory without a network round-trip while younger than this. */
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour
/** Hard staleness guard — older snapshots are refused even as a fallback. */
const MAX_STALENESS_MS = 24 * 60 * 60 * 1000; // 24 hours

export interface FxRateSnapshot {
  base: string;
  date: string;
  rates: Record<string, number>;
  fetchedAt: number;
}

let cache: FxRateSnapshot | null = null;
let inflight: Promise<FxRateSnapshot> | null = null;

async function fetchFrankfurterLatest(): Promise<FxRateSnapshot> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(FRANKFURTER_LATEST_URL, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      throw new Error(`Frankfurter responded HTTP ${res.status}`);
    }
    const data = (await res.json()) as {
      base?: string;
      date?: string;
      rates?: Record<string, unknown>;
    };
    if (
      !data ||
      typeof data !== "object" ||
      !data.rates ||
      typeof data.rates !== "object"
    ) {
      throw new Error("Malformed Frankfurter response (missing rates object)");
    }
    const rates: Record<string, number> = { EUR: 1 };
    for (const [currency, value] of Object.entries(data.rates)) {
      const n = Number(value);
      if (Number.isFinite(n) && n > 0) rates[currency.toUpperCase()] = n;
    }
    const snapshot: FxRateSnapshot = {
      base: String(data.base ?? "EUR").toUpperCase(),
      date: String(data.date ?? ""),
      rates,
      fetchedAt: Date.now(),
    };
    cache = snapshot;
    return snapshot;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Returns the freshest available ECB/Frankfurter snapshot.
 *  - Serves the in-memory cache while younger than CACHE_TTL_MS.
 *  - On refresh failure, serves a stale snapshot only while younger than
 *    MAX_STALENESS_MS; beyond that the feed is treated as down and a
 *    SERVICE_UNAVAILABLE TRPCError is thrown (fail loud — never fabricate).
 */
export async function getFxRateSnapshot(): Promise<FxRateSnapshot> {
  if (cache && Date.now() - cache.fetchedAt < CACHE_TTL_MS) {
    return cache;
  }
  if (!inflight) {
    inflight = fetchFrankfurterLatest().finally(() => {
      inflight = null;
    });
  }
  try {
    return await inflight;
  } catch (err) {
    if (cache && Date.now() - cache.fetchedAt < MAX_STALENESS_MS) {
      console.warn(
        `[FX] Live refresh failed (${err instanceof Error ? err.message : String(err)}); serving cached rates from ${new Date(cache.fetchedAt).toISOString()}`
      );
      return cache;
    }
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Live FX rate feed (Frankfurter/ECB) unavailable and no fresh cached rates: ${err instanceof Error ? err.message : String(err)}`,
    });
  }
}

export interface LiveFxRate {
  fromCurrency: string;
  toCurrency: string;
  rate: number;
  source: "frankfurter/ecb";
  rateDate: string;
  fetchedAt: string;
}

/**
 * Resolves a live cross rate for `from` → `to` from the ECB reference feed.
 * Throws SERVICE_UNAVAILABLE when the feed is down/stale and NOT_IMPLEMENTED
 * when either currency is outside ECB coverage — never returns a fabricated
 * or silent 1:1 rate for unknown currencies.
 */
export async function getLiveFxRate(
  from: string,
  to: string
): Promise<LiveFxRate> {
  const fromCurrency = from.toUpperCase();
  const toCurrency = to.toUpperCase();
  if (fromCurrency === toCurrency) {
    return {
      fromCurrency,
      toCurrency,
      rate: 1,
      source: "frankfurter/ecb",
      rateDate: "same-currency",
      fetchedAt: new Date().toISOString(),
    };
  }
  const snapshot = await getFxRateSnapshot();
  const ageMs = Date.now() - snapshot.fetchedAt;
  if (ageMs > MAX_STALENESS_MS) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `FX rates are stale (${Math.round(ageMs / 60000)} minutes old) — refusing to quote ${fromCurrency}/${toCurrency}`,
    });
  }
  const fromRate = snapshot.rates[fromCurrency];
  const toRate = snapshot.rates[toCurrency];
  if (!fromRate || !toRate) {
    const missing = !fromRate ? fromCurrency : toCurrency;
    throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message: `Currency ${missing} is not covered by the ECB/Frankfurter reference feed — refusing to quote ${fromCurrency}/${toCurrency} with a fabricated rate`,
    });
  }
  return {
    fromCurrency,
    toCurrency,
    rate: toRate / fromRate,
    source: "frankfurter/ecb",
    rateDate: snapshot.date,
    fetchedAt: new Date(snapshot.fetchedAt).toISOString(),
  };
}
