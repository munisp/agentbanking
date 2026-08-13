/**
 * Live FX rates — Frankfurter public API (ECB reference rates).
 *
 * Guarantees:
 * - Real HTTP fetch with a hard timeout (AbortController)
 * - In-process cache keyed by pair, stamped with its fetched-at time
 * - Staleness guard: entries older than FX_RATE_MAX_AGE_MS are refetched;
 *   if the refresh fails the call hard-fails — stale or fabricated rates
 *   are never served
 * - Unknown / unsupported currencies raise an error. There is no silent
 *   1:1 conversion and no hardcoded rate table anywhere on this path.
 */
import { TRPCError } from "@trpc/server";

const FRANKFURTER_BASE_URL =
  process.env.FRANKFURTER_BASE_URL ?? "https://api.frankfurter.dev/v1";
const FX_FETCH_TIMEOUT_MS = 5_000;
const FX_RATE_MAX_AGE_MS = 6 * 60 * 60 * 1000; // 6h — ECB publishes once daily

export interface LiveRate {
  rate: number;
  fetchedAt: string; // ISO timestamp of when the rate was fetched
}

interface RateCacheEntry {
  rate: number;
  fetchedAtMs: number;
}

interface AllRatesCacheEntry {
  rates: Record<string, number>;
  fetchedAtMs: number;
}

const rateCache = new Map<string, RateCacheEntry>();
const allRatesCache = new Map<string, AllRatesCacheEntry>();

async function fetchFrankfurter(path: string): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FX_FETCH_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${FRANKFURTER_BASE_URL}${path}`, {
      signal: controller.signal,
      headers: { accept: "application/json" },
    });
  } catch (err) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Live FX rate service unreachable: ${err instanceof Error ? err.message : "network error"}`,
    });
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 400 || res.status === 404 || res.status === 422) {
    const body = await res.text().catch(() => "");
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Unknown or unsupported currency for ECB reference rates: ${body.slice(0, 200)}`,
    });
  }
  if (!res.ok) {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Live FX rate service returned HTTP ${res.status}`,
    });
  }
  return res.json();
}

/**
 * Returns the live rate for from→to (1 unit of `from` expressed in `to`).
 * Throws TRPCError on unknown currencies, on feed outage, or when only a
 * stale rate would be available — callers must hard-fail, never estimate.
 */
export async function getLiveFxRate(
  fromCurrency: string,
  toCurrency: string
): Promise<LiveRate> {
  const from = fromCurrency.toUpperCase();
  const to = toCurrency.toUpperCase();
  if (!/^[A-Z]{3}$/.test(from) || !/^[A-Z]{3}$/.test(to)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid currency code(s): ${fromCurrency}/${toCurrency}`,
    });
  }
  if (from === to) {
    return { rate: 1, fetchedAt: new Date().toISOString() };
  }
  const key = `${from}-${to}`;
  const now = Date.now();
  const cached = rateCache.get(key);
  if (cached && now - cached.fetchedAtMs <= FX_RATE_MAX_AGE_MS) {
    return {
      rate: cached.rate,
      fetchedAt: new Date(cached.fetchedAtMs).toISOString(),
    };
  }
  const payload = await fetchFrankfurter(
    `/latest?base=${encodeURIComponent(from)}&symbols=${encodeURIComponent(to)}`
  );
  const rate = payload?.rates?.[to];
  if (typeof rate !== "number" || !Number.isFinite(rate) || rate <= 0) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `No live ECB reference rate for pair ${key} (unsupported currency)`,
    });
  }
  rateCache.set(key, { rate, fetchedAtMs: now });
  return { rate, fetchedAt: new Date(now).toISOString() };
}

/**
 * Returns the full live rate set for a base currency (ECB reference set).
 * Cached with the same staleness guard as getLiveFxRate.
 */
export async function getAllLiveFxRates(
  baseCurrency = "EUR"
): Promise<{ base: string; rates: Record<string, number>; fetchedAt: string }> {
  const base = baseCurrency.toUpperCase();
  if (!/^[A-Z]{3}$/.test(base)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid currency code: ${baseCurrency}`,
    });
  }
  const now = Date.now();
  const cached = allRatesCache.get(base);
  if (cached && now - cached.fetchedAtMs <= FX_RATE_MAX_AGE_MS) {
    return {
      base,
      rates: cached.rates,
      fetchedAt: new Date(cached.fetchedAtMs).toISOString(),
    };
  }
  const payload = await fetchFrankfurter(
    `/latest?base=${encodeURIComponent(base)}`
  );
  const rates = payload?.rates;
  if (!rates || typeof rates !== "object") {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Live FX rate feed returned no rates for base ${base}`,
    });
  }
  const clean: Record<string, number> = {};
  for (const [ccy, val] of Object.entries(rates)) {
    if (typeof val === "number" && Number.isFinite(val) && val > 0) {
      clean[ccy] = val;
    }
  }
  allRatesCache.set(base, { rates: clean, fetchedAtMs: now });
  return { base, rates: clean, fetchedAt: new Date(now).toISOString() };
}
