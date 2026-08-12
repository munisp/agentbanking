// @ts-nocheck
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, sql, count, and, gte, lte } from "drizzle-orm";
import { auditLog, systemConfig } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";
import {
  fetchFrankfurterSnapshot,
  fetchFrankfurterTimeseries,
  getFreshFxSnapshot,
  persistFxSnapshot,
} from "../lib/fxRateFeed";

/** Rates older than this are treated as stale on live conversion paths. */
const FX_RATE_STALE_MS = 24 * 60 * 60 * 1000;

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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  cancelled: [],
  archived: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────

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

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishfxRatesMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `platform.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(
    () => {}
  );

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `platform_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `platform_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("platform", {
    ref,
    action,
    ...payload,
    timestamp: ts,
  }).catch(() => {});
}

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
        amount: z.number().min(0).positive(),
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
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as Record<string, unknown>).status as string;
        const currentStatus =
          ((input as Record<string, unknown>).currentStatus as string) ||
          "pending";
        const allowed =
          STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
          });
        }
      }
      const txAmount =
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
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
        await writeAuditLog({
          agentId:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.id ?? 0)
              : 0,

          agentCode:
            typeof ctx === "object" && ctx !== null && "user" in ctx
              ? ((ctx as any).user?.agentCode ?? "system")
              : "system",

          action: "MUTATION",

          resource: "fxRates",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        // Middleware fan-out (fail-open)

        await publishfxRatesMiddleware("updateRates", `${Date.now()}`, {
          action: "updateRates",
        }).catch(() => {});

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
    // Middleware fan-out (fail-open)
    await publishfxRatesMiddleware("currencies", `${Date.now()}`, {
      action: "currencies",
    }).catch(() => {});

    // Real currency list from the fresh live snapshot — never an empty or
    // fabricated list. Throws SERVICE_UNAVAILABLE when no fresh rates exist.
    const snapshot = await getFreshFxSnapshot();
    const currencies = [
      { code: snapshot.base, rate: 1 },
      ...Object.entries(snapshot.rates).map(([code, rate]) => ({
        code,
        rate,
      })),
    ];
    return {
      currencies,
      baseCurrency: snapshot.base,
      fetchedAt: snapshot.fetchedAt,
      source: snapshot.source,
    };
  }),
  refresh: protectedProcedure.mutation(async () => {
    // Middleware fan-out (fail-open)
    await publishfxRatesMiddleware("refresh", `${Date.now()}`, {
      action: "refresh",
    }).catch(() => {});

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
    .query(async () => {
      // Legacy endpoint with no meaningful input mapping — fail loud instead
      // of returning a null stub. Use fxRates.getHistorical for real data.
      throw new TRPCError({
        code: "METHOD_NOT_SUPPORTED",
        message:
          "fxRates.historical is not implemented — use fxRates.getHistorical for live ECB timeseries data.",
      });
    }),
});
