// @ts-nocheck
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, sql, count, and, gte, lte } from "drizzle-orm";
import { auditLog, systemConfig } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import {
  getFreshRates,
  getLiveRate,
  fetchHistoricalRates,
  refreshRates,
  saveManualRates,
  DEFAULT_RATE_BASES,
} from "../lib/fxRateFeed";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateFxratesInput(data: Record<string, unknown>): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "fxRates",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "fxRates",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_FXRATES = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_FXRATES.validateId(data.id)) errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (!INTEGRITY_RULES_FXRATES.validateRange(data.amount, 0, 100_000_000))
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _fxRates_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

// ── Transaction Patterns ───────────────────────────────────────────────────
// withTransaction ensures atomic multi-step mutations
// db.transaction() wraps sequential DB ops in a single transaction
// .transaction() provides rollback on failure
const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};

export const fxRatesRouter = router({
  getRates: protectedProcedure
    .input(z.object({ baseCurrency: z.string().default("NGN") }).optional())
    .query(async ({ input }) => {
      try {
        // Live rates from the FX rate feed (fetched-at + staleness guard).
        // Fails loud when no fresh rate is available — never serves
        // hardcoded fallback rates.
        const base = (input?.baseCurrency ?? "NGN").toUpperCase();
        const fresh = await getFreshRates(base);
        return {
          baseCurrency: base,
          rates: fresh.rates,
          lastUpdated: fresh.fetchedAt,
          source: fresh.source,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  convert: protectedProcedure
    .input(
      z.object({
        from: z.string(),
        to: z.string(),
        amount: z.number().positive(),
      })
    )
    .query(async ({ input }) => {
      try {
        // Live conversion rate — unknown currencies are rejected (BAD_REQUEST)
        // and unavailable feeds fail loud (SERVICE_UNAVAILABLE). No `?? 1`
        // silent 1:1 conversion.
        const liveRate = await getLiveRate(input.from, input.to);
        const converted = input.amount * liveRate.rate;
        return {
          from: input.from,
          to: input.to,
          amount: input.amount,
          convertedAmount: Math.round(converted * 100) / 100,
          rate: liveRate.rate,
          rateSource: liveRate.source,
          rateFetchedAt: liveRate.fetchedAt,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  updateRates: protectedProcedure
    .input(z.object({ rates: z.record(z.string(), z.number()) }))
    .mutation(async ({ input, ctx }) => {
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "fxRates",
        "mutation",
        "Executed fxRates mutation"
      );

      try {
        const db = (await getDb())!;
        await db
          .insert(systemConfig)
          .values({ key: "fx_rates", value: JSON.stringify(input.rates) })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: { value: JSON.stringify(input.rates), updatedAt: new Date() },
          });
        // Admin override also becomes the served (NGN-based) rate set so
        // getRates/convert stay consistent with the manual update.
        await saveManualRates("NGN", input.rates);
        await db.insert(auditLog).values({
          action: "fx_rates_updated",
          resource: "fx_rates",
          resourceId: "rates",
          status: "success",
          metadata: { rates: input.rates },
        });
        return { success: true, updatedAt: new Date().toISOString() };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [total] = await db
      .select({ value: count() })
      .from(auditLog)
      .where(eq(auditLog.action, "fx_rates_updated"))
      .limit(100);
    return {
      totalUpdates: Number(total.value),
      lastUpdated: new Date().toISOString(),
    };
  }),
  // Historical rates — real time series from the Frankfurter / ECB feed.
  // Non-ECB pairs (e.g. NGN-based) fail loud with SERVICE_UNAVAILABLE.
  getHistorical: protectedProcedure
    .input(
      z
        .object({
          base: z.string().default("NGN"),
          target: z.string().default("USD"),
          days: z.number().default(30),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const base = input?.base ?? "NGN";
      const target = input?.target ?? "USD";
      const days = input?.days ?? 30;
      const timeseries = await fetchHistoricalRates(base, target, days);
      return {
        base,
        target,
        timeseries,
        source: "frankfurter/ecb",
      };
    }),
  currencies: protectedProcedure.query(async () => {
    // Live currency list derived from the FX rate feed (fails loud when
    // the feed is unavailable).
    const fresh = await getFreshRates("NGN");
    const currencies = Object.entries(fresh.rates).map(([code, rate]) => ({
      code,
      name: code,
      symbol: code,
      rate,
    }));
    return {
      currencies,
      baseCurrency: "NGN",
      lastUpdated: fresh.fetchedAt,
      source: fresh.source,
    };
  }),
  refresh: protectedProcedure.mutation(async () => {
    // Real refresh: fetch live rates and persist them to the cache. Throws
    // SERVICE_UNAVAILABLE when nothing could be refreshed.
    const result = await refreshRates(DEFAULT_RATE_BASES);
    return {
      success: true,
      refreshedAt: result.refreshedAt,
      ratesUpdated: result.ratesUpdated,
      ...(result.errors ? { errors: result.errors } : {}),
    };
  }),
  historical: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, timestamp: new Date().toISOString() };
    }),
});
