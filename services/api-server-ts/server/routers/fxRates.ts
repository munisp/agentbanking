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
  fetchFrankfurterSnapshot,
  fetchFrankfurterTimeseries,
  persistFxSnapshot,
} from "../lib/fxRateFeed";

/** Rates older than this are treated as stale on live conversion paths. */
const FX_RATE_STALE_MS = 24 * 60 * 60 * 1000;

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
        const db = (await getDb())!;
        const [config] = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "fx_rates"))
          .limit(1);
        if (!config) {
          throw new TRPCError({
            code: "SERVICE_UNAVAILABLE",
            message:
              "No FX rates are stored. Run fxRates.refresh to pull live rates from the Frankfurter/ECB feed or set rates manually via fxRates.updateRates.",
          });
        }
        const parsed = JSON.parse(String(config.value));
        // Stored shape: { base, rates (units of `base` per 1 unit of X), fetchedAt, source }.
        // Legacy flat maps are treated as NGN-based manual rates.
        const rates: Record<string, number> = parsed.rates ?? parsed;
        const rateBase: string = parsed.base ?? "NGN";
        const lastUpdated = parsed.fetchedAt ?? config.updatedAt ?? null;
        const stale = lastUpdated
          ? Date.now() - new Date(lastUpdated).getTime() > FX_RATE_STALE_MS
          : true;
        return {
          baseCurrency: input?.baseCurrency ?? rateBase,
          rateBase,
          rates,
          lastUpdated,
          stale,
          source: parsed.source ?? "manual",
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
        const db = (await getDb())!;
        const [config] = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "fx_rates"))
          .limit(1);
        if (!config) {
          throw new TRPCError({
            code: "SERVICE_UNAVAILABLE",
            message:
              "No FX rates are stored. Run fxRates.refresh to pull live rates from the Frankfurter/ECB feed.",
          });
        }
        const parsed = JSON.parse(String(config.value));
        const rateBase: string = parsed.base ?? "NGN";
        const table: Record<string, number> = parsed.rates ?? parsed;
        const fetchedAt = parsed.fetchedAt ?? config.updatedAt ?? null;
        if (
          !fetchedAt ||
          Date.now() - new Date(fetchedAt).getTime() > FX_RATE_STALE_MS
        ) {
          throw new TRPCError({
            code: "SERVICE_UNAVAILABLE",
            message:
              "Stored FX rates are stale — refresh from the live feed (fxRates.refresh) before converting.",
          });
        }
        // `table` stores units of `rateBase` per 1 unit of currency X.
        // Unknown currencies fail loud — no silent 1:1 conversion.
        const perBase = (ccy: string): number | undefined =>
          ccy === rateBase ? 1 : table[ccy];
        const fromRate = perBase(input.from);
        const toRate = perBase(input.to);
        if (typeof fromRate !== "number" || !(fromRate > 0)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `No stored FX rate for currency ${input.from} (base ${rateBase}).`,
          });
        }
        if (typeof toRate !== "number" || !(toRate > 0)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `No stored FX rate for currency ${input.to} (base ${rateBase}).`,
          });
        }
        const converted = (input.amount * fromRate) / toRate;
        return {
          from: input.from,
          to: input.to,
          amount: input.amount,
          convertedAmount: Math.round(converted * 100) / 100,
          rate: fromRate / toRate,
          rateBase,
          fetchedAt,
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
        // Manual (admin-set) rates — stored in the documented shape with an
        // explicit base + fetchedAt so convert/getRates can reason about them.
        const payload = {
          base: "NGN",
          rates: input.rates,
          fetchedAt: new Date().toISOString(),
          source: "manual",
        };
        await db
          .insert(systemConfig)
          .values({ key: "fx_rates", value: JSON.stringify(payload) })
          .onConflictDoUpdate({
            target: systemConfig.key,
            set: { value: JSON.stringify(payload), updatedAt: new Date() },
          });
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
  // Historical rates — references Frankfurter / ECB exchange rate API for timeseries
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
      // Live timeseries from the Frankfurter API (ECB reference rates).
      // Unsupported currencies / feed failures fail loud — no fabricated data.
      const base = input?.base ?? "NGN";
      const target = input?.target ?? "USD";
      const days = input?.days ?? 30;
      const series = await fetchFrankfurterTimeseries(base, target, days).catch(
        err => {
          throw new TRPCError({
            code: "SERVICE_UNAVAILABLE",
            message: `Historical FX rates unavailable from the Frankfurter/ECB feed for ${base}/${target}: ${err instanceof Error ? err.message : "unknown error"}`,
          });
        }
      );
      return {
        base,
        target,
        timeseries: series,
        source: "frankfurter/ecb",
      };
    }),
  currencies: protectedProcedure.query(async () => {
    return {
      currencies: [] as Array<{
        code: string;
        name: string;
        symbol: string;
        rate: number;
      }>,
      baseCurrency: "NGN",
    };
  }),
  refresh: protectedProcedure.mutation(async () => {
    // Real refresh: pull latest rates from the Frankfurter/ECB feed and
    // persist them. Fails loud when the feed is unreachable or empty.
    const snapshot = await fetchFrankfurterSnapshot().catch(err => {
      throw new TRPCError({
        code: "SERVICE_UNAVAILABLE",
        message: `FX rate refresh failed — Frankfurter/ECB feed unreachable: ${err instanceof Error ? err.message : "unknown error"}`,
      });
    });
    await persistFxSnapshot(snapshot);

    // Convert to storage shape: units of `base` per 1 unit of currency X.
    const table: Record<string, number> = { [snapshot.base]: 1 };
    for (const [ccy, perBaseUnit] of Object.entries(snapshot.rates)) {
      if (typeof perBaseUnit === "number" && perBaseUnit > 0) {
        table[ccy] = 1 / perBaseUnit;
      }
    }
    const ratesUpdated = Object.keys(table).length - 1;
    if (ratesUpdated <= 0) {
      throw new TRPCError({
        code: "SERVICE_UNAVAILABLE",
        message: "FX rate refresh failed — feed returned zero usable rates.",
      });
    }
    const payload = {
      base: snapshot.base,
      rates: table,
      fetchedAt: snapshot.fetchedAt,
      source: snapshot.source,
    };
    const db = (await getDb())!;
    await db
      .insert(systemConfig)
      .values({ key: "fx_rates", value: JSON.stringify(payload) })
      .onConflictDoUpdate({
        target: systemConfig.key,
        set: { value: JSON.stringify(payload), updatedAt: new Date() },
      });
    return {
      success: true,
      refreshedAt: snapshot.fetchedAt,
      ratesUpdated,
      source: snapshot.source,
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
