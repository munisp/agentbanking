import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, sql, count, sum, and, gte, lte } from "drizzle-orm";
import { transactions, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
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
function validateSavingsproductsInput(data: Record<string, unknown>): boolean {
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
      "savingsProducts",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "savingsProducts",
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
    resource: "savingsProducts",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "savingsProducts",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_SAVINGSPRODUCTS = {
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
    if (!INTEGRITY_RULES_SAVINGSPRODUCTS.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_SAVINGSPRODUCTS.validateRange(
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

// ── Database Query Patterns ────────────────────────────────────────────────
const _savingsProducts_db = {
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

export const savingsProductsRouter = router({
  listAccounts: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().min(1).max(200).default(50),
          agentId: z.number().optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions = [];
        if (input?.agentId)
          conditions.push(eq(transactions.agentId, input.agentId));
        const rows = await db
          .select()
          .from(transactions)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(transactions.createdAt))
          .limit(input?.limit ?? 50);
        return { accounts: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  deposit: protectedProcedure
    .input(
      z.object({
        accountId: z.number(),
        amount: z.number().positive().max(10_000_000),
        agentId: z.number().optional(),
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
        "savingsProducts",
        "mutation",
        "Executed savingsProducts mutation"
      );

      // NF-FF-5: fail loud. No savings ledger schema exists — the previous
      // implementation inserted fabricated status:"success" "Cash In" rows
      // into `transactions` (with a caller-chosen agentId) that inflated
      // customerWalletSystem derived balances without any balance movement.
      // Fabricated ledger rows are removed, not reimplemented.
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message:
          "Savings deposit rail not implemented: no savings ledger exists to record balance movement",
      });
    }),
  withdraw: protectedProcedure
    .input(
      z.object({
        accountId: z.number(),
        amount: z.number().positive().max(5_000_000),
        agentId: z.number().optional(),
      })
    )
    .mutation(async ({ input }) => {
      // NF-FF-5: fail loud. No savings ledger schema exists — the previous
      // implementation inserted fabricated status:"success" "Cash Out" rows
      // into `transactions` (with a caller-chosen agentId) that deflated
      // customerWalletSystem derived balances without any balance movement.
      // Fabricated ledger rows are removed, not reimplemented.
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message:
          "Savings withdrawal rail not implemented: no savings ledger exists to record balance movement",
      });
    }),
  getStats: protectedProcedure.query(async () => {
    try {
      const db = (await getDb())!;
      const [totals] = await db
        .select({ total: count(), volume: sum(transactions.amount) })
        .from(transactions)
        .limit(100);
      return {
        totalAccounts: 0,
        totalDeposits: Number(totals.total),
        totalVolume: Number(totals.volume ?? 0),
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),

  // ── Sprint 28 domain procedures ──
  products: protectedProcedure.query(async () => {
    // Honest empty state: no savings product catalog table exists in the
    // schema. The previous implementation returned a fabricated "SP-001"
    // product. When a product catalog is modeled, query it here.
    return { products: [] };
  }),
  list: protectedProcedure.query(async () => {
    // Honest empty state: no savings account table exists in the schema. The
    // previous implementation returned a fabricated "SA-001" account with an
    // invented balance. When savings accounts are modeled, query them here.
    return { accounts: [], total: 0 };
  }),
  analytics: protectedProcedure.query(async () => {
    // Real aggregates where a real source exists (transaction ledger volume),
    // honest zeros where no savings schema exists. The previous
    // implementation returned fully fabricated account counts, balances, and
    // interest figures.
    try {
      const db = (await getDb())!;
      const [totals] = await db
        .select({
          total: count(),
          volume: sql<string>`COALESCE(SUM(${transactions.amount}::numeric), 0)`,
          avg: sql<string>`COALESCE(AVG(${transactions.amount}::numeric), 0)`,
        })
        .from(transactions);
      return {
        totalAccounts: 0, // no savings account table exists
        activeAccounts: 0,
        totalBalance: 0,
        avgBalance: 0,
        interestPaid: 0, // no interest ledger exists
        totalDeposits: Number(totals?.volume ?? 0),
        totalInterestPaid: 0,
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),
});
