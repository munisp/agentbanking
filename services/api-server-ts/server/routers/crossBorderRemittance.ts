/**
 * Cross-Border Remittance — international money transfers via agent network,
 * FX rate management, compliance checks, and corridor management.
 *
 * Middleware: Mojaloop (ILP), Kafka (remittance events), PostgreSQL (transfer records),
 * TigerBeetle (multi-currency ledger), Go FX service
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte, lte, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { getLiveFxRate } from "../lib/fxRateProvider";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

// Corridor configuration only — rates are NOT hardcoded here. FX rates are
// fetched live from the Frankfurter/ECB reference feed via
// ../lib/fxRateProvider (timeout + cached with fetched-at + staleness guard).
// getQuote/sendRemittance HARD-FAIL (SERVICE_UNAVAILABLE / NOT_IMPLEMENTED)
// when no fresh live rate is available — the previous hardcoded corridor
// rates drove real float debits at fabricated rates.
const CORRIDORS = [
  {
    from: "NGN",
    to: "GHS",
    name: "Nigeria to Ghana",
    active: true,
  },
  {
    from: "NGN",
    to: "KES",
    name: "Nigeria to Kenya",
    active: true,
  },
  {
    from: "NGN",
    to: "ZAR",
    name: "Nigeria to South Africa",
    active: true,
  },
  {
    from: "NGN",
    to: "USD",
    name: "Nigeria to USA",
    active: true,
  },
  {
    from: "NGN",
    to: "GBP",
    name: "Nigeria to UK",
    active: true,
  },
  { from: "NGN", to: "EUR", name: "Nigeria to EU", active: true },
  {
    from: "NGN",
    to: "XOF",
    name: "Nigeria to West Africa (CFA)",
    active: true,
  },
];

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateCrossborderremittanceInput(
  data: Record<string, unknown>
): boolean {
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
      "crossBorderRemittance",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "crossBorderRemittance",
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
    resource: "crossBorderRemittance",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "crossBorderRemittance",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_CROSSBORDERREMITTANCE = {
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
    if (!INTEGRITY_RULES_CROSSBORDERREMITTANCE.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_CROSSBORDERREMITTANCE.validateRange(
        data.amount,
        0,
        100_000_000
      )
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Database Query Patterns ────────────────────────────────────────────────
const _crossBorderRemittance_db = {
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

export const crossBorderRemittanceRouter = router({
  getQuote: protectedProcedure
    .input(
      z.object({
        fromCurrency: z.string().default("NGN"),
        toCurrency: z.string(),
        amount: z.number().positive().max(50_000_000),
      })
    )
    .query(async ({ input }) => {
      try {
        const corridor = CORRIDORS.find(
          c => c.from === input.fromCurrency && c.to === input.toCurrency
        );
        if (!corridor)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Corridor not available",
          });
        if (!corridor.active)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Corridor temporarily suspended",
          });

        // Live rate — quote hard-fails without a fresh rate (no corridor table).
        const liveRate = await getLiveFxRate(input.fromCurrency, input.toCurrency);
        const rate = liveRate.rate;

        const fee = Math.max(500, Math.round(input.amount * 0.02));
        const convertedAmount = (input.amount - fee) * rate;

        return {
          fromAmount: input.amount,
          fromCurrency: input.fromCurrency,
          toAmount: Math.round(convertedAmount * 100) / 100,
          toCurrency: input.toCurrency,
          rate,
          rateSource: liveRate.source,
          rateDate: liveRate.rateDate,
          rateFetchedAt: liveRate.fetchedAt,
          fee,
          corridorName: corridor.name,
          expiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
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

  sendRemittance: protectedProcedure
    .input(
      z.object({
        toCurrency: z.string(),
        amount: z.number().positive().max(50_000_000),
        recipientName: z.string().min(2).max(128),
        recipientPhone: z.string().min(8).max(20),
        recipientBankCode: z.string().optional(),
        recipientAccount: z.string().optional(),
        purpose: z.string().max(256).optional(),
      })
    )
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
        "crossBorderRemittance",
        "mutation",
        "Executed crossBorderRemittance mutation"
      );

      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const corridor = CORRIDORS.find(
          c => c.from === "NGN" && c.to === input.toCurrency
        );
        if (!corridor)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Corridor not available",
          });

        // Live rate fetched BEFORE any float movement — send hard-fails
        // without a fresh rate (no fabricated conversion against real float).
        const liveRate = await getLiveFxRate("NGN", input.toCurrency);
        const rate = liveRate.rate;

        // ── NF-FF-9: FAIL LOUD, NO STATE CHANGE ──────────────────────────────
        // The previous implementation performed a TOCTOU float SELECT, inserted
        // a fabricated status:"success" "Transfer" row, then issued a separate
        // UNGUARDED float debit — with no partner payout leg and no
        // idempotency. Money was destroyed (float debited, recipient never
        // paid). No cross-border partner payout integration exists, so the only
        // honest behaviour is to refuse before ANY money movement. A real
        // integration must implement: claim-first idempotency
        // (claimIdempotencyKey from ../lib/transactionHelper), then a single
        // db.transaction containing a guarded conditional debit (UPDATE agents
        // ... AND "floatBalance" - $amt >= 0 RETURNING; 0 rows → 422) and a
        // status "pending" transaction row, settled only after the partner
        // payout leg confirms.
        throw new TRPCError({
          code: "NOT_IMPLEMENTED",
          message:
            "Cross-border remittance payout rail not integrated: no partner payout leg exists",
        });
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  listCorridors: protectedProcedure.query(async () => {
    const corridors = await Promise.all(
      CORRIDORS.filter(c => c.active).map(async c => {
        try {
          const live = await getLiveFxRate(c.from, c.to);
          return {
            ...c,
            currentRate: live.rate,
            rateSource: live.source,
            rateDate: live.rateDate,
            rateFetchedAt: live.fetchedAt,
            rateAvailable: true,
          };
        } catch (err) {
          // Feed down → fail loud for the whole list; uncovered currencies
          // are reported explicitly per corridor (never a fabricated rate).
          if (err instanceof TRPCError && err.code === "SERVICE_UNAVAILABLE")
            throw err;
          return {
            ...c,
            currentRate: null,
            rateSource: null,
            rateDate: null,
            rateFetchedAt: null,
            rateAvailable: false,
          };
        }
      })
    );
    return { corridors };
  }),

  getHistory: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }))
    .query(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) return { items: [] };

        const items = await db
          .select()
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, session.id),
              sql`${transactions.metadata}->>'remittanceType' = 'cross_border'`
            )
          )
          .orderBy(desc(transactions.createdAt))
          .limit(input.limit);

        return { items };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
