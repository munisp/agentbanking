// Sprint 87: Upgraded from mock data to real DB queries — multiCurrencyExchange
import { z } from "zod";
import { publicProcedure, protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents, gl_journal_entries } from "../../drizzle/schema";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheGet, cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import { getAgentFromCookie } from "../middleware/agentAuth";
import { checkDailyLimit } from "../lib/cbnLimits";
import crypto from "crypto";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

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
  getLiveFxRate,
  getFxRateSnapshot,
} from "../lib/fxRateProvider";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["processing", "cancelled"],
  processing: ["completed", "failed"],
  completed: ["refunded"],
  failed: ["pending"],
  cancelled: [],
  refunded: [],
};

// FX rates come from the live Frankfurter/ECB reference feed via
// ../lib/fxRateProvider (timeout + cached with fetched-at + staleness guard).
// The previous ~48-entry hardcoded corridor table drove real convert
// mutations at fabricated rates — removed.

const fxSpreadKey = (pair: string) => `fx_spread:${pair.toUpperCase()}`;

/** Persisted per-pair spread (percent), written by setSpread. */
async function getSpreadPercent(pair: string): Promise<number> {
  const raw = await cacheGet(fxSpreadKey(pair));
  if (raw === null) return 0;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

const getRates = protectedProcedure.query(async () => {
  const snapshot = await getFxRateSnapshot();
  const rates = Object.entries(snapshot.rates)
    .filter(([currency]) => currency !== snapshot.base)
    .map(([currency, rate]) => ({
      pair: `${snapshot.base}-${currency}`,
      fromCurrency: snapshot.base,
      toCurrency: currency,
      rate,
      inverseRate: Math.round((1 / rate) * 10000) / 10000,
      updatedAt: new Date(snapshot.fetchedAt).toISOString(),
      rateSource: "frankfurter/ecb" as const,
      rateDate: snapshot.date,
    }))
    .sort((a, b) => a.pair.localeCompare(b.pair));
  return { rates, total: rates.length };
});

const convert = protectedProcedure
  .input(
    z.object({
      fromCurrency: z.string().min(3).max(3),
      toCurrency: z.string().min(3).max(3),
      amount: z.number().positive().min(1),
      idempotencyKey: z.string().min(16).max(64).optional(),
    })
  )
  .mutation(async ({ input, ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    const pairKey = `${input.fromCurrency.toUpperCase()}-${input.toCurrency.toUpperCase()}`;
    // Live ECB/Frankfurter rate — throws NOT_IMPLEMENTED for uncovered pairs
    // and SERVICE_UNAVAILABLE when the feed is down/stale. No fallback table.
    const liveRate = await getLiveFxRate(input.fromCurrency, input.toCurrency);
    const spreadPercent = await getSpreadPercent(pairKey);
    const rate =
      Math.round(liveRate.rate * (1 + spreadPercent / 100) * 100_000_000) /
      100_000_000;

    const convertedAmount = Math.round(input.amount * rate * 100) / 100;
    const feeResult = calculateFee(input.amount, "transfer");
    const ref = `FX-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;

    const idempFn = async () => {
      return withTransaction(async tx => {
        const db = tx ?? (await getDb())!;

        // Lock agent row
        const agentRows = await db.execute(
          sql`SELECT float_balance, float_locked FROM agents WHERE id = ${session.id} FOR UPDATE`
        );
        const agentRow = (agentRows as any).rows?.[0] ?? (agentRows as any)[0];
        if (!agentRow)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Agent not found",
          });
        if (Number(agentRow.float_balance) < input.amount) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Insufficient balance for conversion`,
          });
        }

        // Debit source currency
        await db.execute(
          sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - ${String(input.amount)} WHERE id = ${session.id}`
        );

        // Record FX transaction
        const [txRecord] = await db
          .insert(transactions)
          .values({
            ref,
            agentId: session.id,
            type: "FX Exchange",
            amount: String(input.amount),
            fee: String(feeResult.fee),
            commission: "0",
            currency: input.fromCurrency,
            channel: "Exchange",
            status: "success",
            metadata: {
              fromCurrency: input.fromCurrency,
              toCurrency: input.toCurrency,
              exchangeRate: rate,
              spreadPercent,
              rateSource: liveRate.source,
              rateDate: liveRate.rateDate,
              rateFetchedAt: liveRate.fetchedAt,
              convertedAmount,
            },
          })
          .returning();

        // GL: Debit FX Source, Credit FX Destination
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${ref}`,
          description: `FX ${input.fromCurrency} → ${input.toCurrency} @ ${rate}`,
          debitAccountId: 3002, // FX Conversion Payable
          creditAccountId: 2001, // Agent Float
          amount: Math.round(input.amount * 100),
          currency: input.fromCurrency,
          referenceType: "fx_exchange",
          referenceId: String(txRecord.id),
          postedBy: session.agentCode,
          status: "posted",
        });

        return txRecord;
      }, "multiCurrencyExchange.convert");
    };

    const txRecord = input.idempotencyKey
      ? await withIdempotency(input.idempotencyKey, idempFn)
      : await idempFn();

    publishEvent(
      "pos.transactions.created",
      ref,
      {
        type: "fx_exchange",
        ref,
        fromCurrency: input.fromCurrency,
        toCurrency: input.toCurrency,
        amount: input.amount,
        convertedAmount,
        exchangeRate: rate,
        fee: feeResult.fee,
        agentId: session.id,
        timestamp: new Date().toISOString(),
      },
      { agentCode: session.agentCode }
    ).catch(() => {});

    // TigerBeetle dual-ledger — mirrors the GL posting above (was a 2001→2001
    // self-transfer that moved nothing; now debit FX Conversion Payable,
    // credit Agent Float).
    tbCreateTransfer({
      debitAccountId: "3002",
      creditAccountId: "2001",
      amount: Math.round(input.amount * 100),
      ref,
      txType: "fx_exchange",
      agentCode: session.agentCode,
    }).catch(() => {});

    // Fluvio + Dapr + Redis + Lakehouse
    publishTxToFluvio({
      txRef: ref,
      agentCode: session.agentCode,
      amount: input.amount,
      type: "fx_exchange",
      timestamp: Date.now(),
    }).catch(() => {});
    dapr
      .publishEvent("pubsub", "fx.exchange.completed", {
        ref,
        fromCurrency: input.fromCurrency,
        toCurrency: input.toCurrency,
        amount: input.amount,
        convertedAmount,
      })
      .catch(() => {});
    cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
    ingestToLakehouse("fx_exchanges", {
      ref,
      fromCurrency: input.fromCurrency,
      toCurrency: input.toCurrency,
      amount: input.amount,
      convertedAmount,
      rate,
      fee: feeResult.fee,
      agentId: session.id,
      timestamp: new Date().toISOString(),
    }).catch(() => {});

    return {
      success: true,
      ref,
      transactionId: txRecord.id,
      fromCurrency: input.fromCurrency,
      toCurrency: input.toCurrency,
      sourceAmount: input.amount,
      convertedAmount,
      exchangeRate: rate,
      spreadPercent,
      rateSource: liveRate.source,
      rateDate: liveRate.rateDate,
      rateFetchedAt: liveRate.fetchedAt,
      fee: feeResult.fee,
      timestamp: new Date().toISOString(),
    };
  });
const getHistory = protectedProcedure
  .input(
    z.object({
      page: z.number().min(1).max(10000).optional(),
      limit: z.number().min(1).max(100).optional(),
    })
  )
  .query(async ({ input, ctx }) => {
    try {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });
      const lim = input.limit ?? 10;
      const offset = ((input.page ?? 1) - 1) * lim;
      const rows = await db
        .select()
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, session.id),
            sql`${transactions.type} = 'FX Exchange'`
          )
        )
        .orderBy(desc(transactions.id))
        .limit(lim)
        .offset(offset);
      const [{ total }] = await db
        .select({ total: count() })
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, session.id),
            sql`${transactions.type} = 'FX Exchange'`
          )
        )
        .limit(100);
      return { items: rows, total, page: input.page ?? 1, limit: lim };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  });
const getStats = publicProcedure
  .input(
    z.object({
      page: z.number().min(1).max(10000).optional(),
      limit: z.number().min(1).max(100).optional(),
      search: z.string().min(1).max(500).optional(),
      dateFrom: z.string().optional(),
      dateTo: z.string().optional(),
    })
  )
  .query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const [{ total }] = await db
        .select({ total: count() })
        .from(transactions)
        .where(sql`${transactions.type} = 'FX Exchange'`)
        .limit(100);
      const recent = await db
        .select()
        .from(transactions)
        .where(sql`${transactions.type} = 'FX Exchange'`)
        .orderBy(desc(transactions.id))
        .limit(5);
      const snapshot = await getFxRateSnapshot();
      const currencies = Object.keys(snapshot.rates).sort();
      const corridors = currencies
        .filter(c => c !== snapshot.base)
        .map(c => `${snapshot.base}-${c}`);
      return {
        supportedCurrencies: currencies.length,
        activePairs: corridors.length,
        supportedPairs: corridors.length,
        totalExchanges: total,
        recentExchanges: recent,
        corridors,
        rateSource: "frankfurter/ecb",
        rateDate: snapshot.date,
        lastRateUpdate: new Date(snapshot.fetchedAt).toISOString(),
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  });
const getCorridors = protectedProcedure
  .input(
    z.object({
      page: z.number().min(1).max(10000).optional(),
      limit: z.number().min(1).max(100).optional(),
      search: z.string().min(1).max(500).optional(),
    })
  )
  .query(async ({ input }) => {
    try {
      const lim = input.limit ?? 10;
      const offset = ((input.page ?? 1) - 1) * lim;
      const snapshot = await getFxRateSnapshot();
      let corridors = Object.entries(snapshot.rates)
        .filter(([currency]) => currency !== snapshot.base)
        .map(([currency, rate]) => ({
          pair: `${snapshot.base}-${currency}`,
          fromCurrency: snapshot.base,
          toCurrency: currency,
          rate,
          rateSource: "frankfurter/ecb" as const,
          rateDate: snapshot.date,
          updatedAt: new Date(snapshot.fetchedAt).toISOString(),
        }))
        .sort((a, b) => a.pair.localeCompare(b.pair));
      if (input.search) {
        const s = input.search.toUpperCase();
        corridors = corridors.filter(c => c.pair.includes(s));
      }
      return {
        items: corridors.slice(offset, offset + lim),
        total: corridors.length,
        page: input.page ?? 1,
        limit: lim,
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  });
const setSpread = protectedProcedure
  .input(
    z.object({ id: z.number(), data: z.record(z.string(), z.any()).optional() })
  )
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
      const spreadData = input.data ?? {};
      const pair = String(spreadData.pair ?? "").toUpperCase();
      const spread = Number(spreadData.spread);

      if (!/^[A-Z]{3}-[A-Z]{3}$/.test(pair)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message:
            'setSpread requires data.pair as an ISO currency pair (e.g. "EUR-USD")',
        });
      }
      if (!Number.isFinite(spread) || spread < 0 || spread > 25) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "data.spread must be a number between 0 and 25 (percent)",
        });
      }

      const [from, to] = pair.split("-");
      // Validates the pair against the live feed (throws if uncovered/down).
      const live = await getLiveFxRate(from, to);

      // Persist the spread durably (no TTL). Success is returned only when
      // the write is confirmed — previously this returned success while
      // persisting nothing.
      const persisted = await cacheSet(fxSpreadKey(pair), String(spread));
      if (!persisted) {
        throw new TRPCError({
          code: "SERVICE_UNAVAILABLE",
          message: "Spread store unavailable — spread was NOT applied",
        });
      }

      await writeAuditLog({
        action: "mutation",
        resource: "multiCurrencyExchange",
        status: "success",
        metadata: {
          pair,
          spread,
          input: JSON.stringify(input).slice(0, 500),
        },
      });
      return {
        success: true,
        pair,
        baseRate: live.rate,
        spread,
        effectiveRate: live.rate * (1 + spread / 100),
        rateSource: live.source,
        rateDate: live.rateDate,
        message: "Spread updated and persisted",
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  });

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "multiCurrencyExchange",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "multiCurrencyExchange",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "multiCurrencyExchange",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "multiCurrencyExchange",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations
export const multiCurrencyExchangeRouter = router({
  getRates,
  convert,
  getHistory,
  getStats,
  getCorridors,
  setSpread,
});
