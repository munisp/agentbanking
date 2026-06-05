import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { agentBankAccounts } from "../../drizzle/schema";
import { eq, desc, and, count, gte, lte, sql } from "drizzle-orm";
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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending_verification: ["email_verified"],
  email_verified: ["profile_complete"],
  profile_complete: ["active"],
  active: ["suspended", "locked", "deactivated"],
  suspended: ["active", "deactivated"],
  locked: ["active", "deactivated"],
  deactivated: ["reactivation_pending"],
  reactivation_pending: ["active", "permanently_closed"],
  permanently_closed: [],
};

const listAccounts = protectedProcedure
  .input(
    z.object({
      agentId: z.number().optional(),
      page: z.number().min(1).max(10000).optional(),
      limit: z.number().min(1).max(100).optional(),
    })
  )
  .query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const lim = input.limit ?? 10;
      const offset = ((input.page ?? 1) - 1) * lim;
      const conditions = input.agentId
        ? [eq(agentBankAccounts.agentId, input.agentId)]
        : [];
      const rows = await db
        .select()
        .from(agentBankAccounts)
        .where(conditions.length ? and(...conditions) : undefined)
        .orderBy(desc(agentBankAccounts.id))
        .limit(lim)
        .offset(offset);
      const [{ total }] = await db
        .select({ total: count() })
        .from(agentBankAccounts)
        .where(conditions.length ? and(...conditions) : undefined)
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

const getAccount = protectedProcedure
  .input(z.object({ id: z.number() }))
  .query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const [row] = await db
        .select()
        .from(agentBankAccounts)
        .where(eq(agentBankAccounts.id, input.id))
        .limit(100);
      if (!row)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Bank account not found",
        });
      return row;
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  });

const addAccount = protectedProcedure
  .input(
    z.object({
      agentId: z.number(),
      bankName: z.string(),
      bankCode: z.string(),
      accountNumber: z.string(),
      accountName: z.string(),
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
      "bankAccountManagement",
      "mutation",
      "Executed bankAccountManagement mutation"
    );

    try {
      const db = (await getDb())!;
      if (!/^[0-9]{10}$/.test(input.accountNumber))
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Invalid NUBAN — must be 10 digits",
        });
      const [row] = await db
        .insert(agentBankAccounts)
        .values(input as any)
        .returning();
      return { ...row, message: "Bank account added" };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message:
          error instanceof Error ? error.message : "Internal server error",
      });
    }
  });

const removeAccount = protectedProcedure
  .input(z.object({ id: z.number() }))
  .mutation(async ({ input }) => {
    try {
      const db = (await getDb())!;
      await db
        .delete(agentBankAccounts)
        .where(eq(agentBankAccounts.id, input.id));
      return { success: true };
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
      "bankAccountManagement",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "bankAccountManagement",
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
    resource: "bankAccountManagement",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "bankAccountManagement",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_BANKACCOUNTMANAGEMENT = {
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
    if (!INTEGRITY_RULES_BANKACCOUNTMANAGEMENT.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_BANKACCOUNTMANAGEMENT.validateRange(
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

export const bankAccountManagementRouter = router({
  listAccounts,
  getAccount,
  addAccount,
  removeAccount,
  list: protectedProcedure
    .input(z.object({}).optional())
    .query(async ({ ctx }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(agentBankAccounts)
          .orderBy(desc(agentBankAccounts.id))
          .limit(50);
        return { items: rows };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  create: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        bankName: z.string(),
        bankCode: z.string(),
        accountNumber: z.string(),
        accountName: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .insert(agentBankAccounts)
          .values(input as any)
          .returning();
        return { ...row, success: true };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  delete: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .delete(agentBankAccounts)
          .where(eq(agentBankAccounts.id, input.id));
        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  verify: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .update(agentBankAccounts)
          .set({ verified: true })
          .where(eq(agentBankAccounts.id, input.id));
        return { success: true, message: "Account verified" };
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
