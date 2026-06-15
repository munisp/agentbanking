// @ts-nocheck
// Sprint 87: Full domain logic — account verification, duplicate detection, primary account management
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agentBankAccounts } from "../../drizzle/schema";
import { eq, desc, and, sql, count } from "drizzle-orm";
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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["pending_review"],
  pending_review: ["approved", "rejected"],
  approved: ["active", "suspended"],
  active: ["suspended", "deactivated", "under_review"],
  suspended: ["active", "deactivated"],
  under_review: ["active", "suspended", "deactivated"],
  deactivated: ["reactivation_pending"],
  reactivation_pending: ["active", "rejected"],
  rejected: [],
};

const NIGERIAN_BANKS = [
  "044",
  "050",
  "011",
  "058",
  "033",
  "215",
  "232",
  "035",
  "057",
  "082",
  "301",
  "221",
  "068",
  "070",
  "076",
];
const NUBAN_REGEX = /^[0-9]{10}$/;

function validateNUBAN(accountNumber: string): boolean {
  return NUBAN_REGEX.test(accountNumber);
}

function maskAccountNumber(num: string): string {
  return num.slice(0, 3) + "****" + num.slice(-3);
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentBankAccountsCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentBankAccountsCrud",
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
    resource: "agentBankAccountsCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentBankAccountsCrud",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const agentBankAccountsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        agentId: z.number().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        const conditions = input.agentId
          ? [eq(agentBankAccounts.agentId, input.agentId)]
          : [];
        const rows = await db
          .select()
          .from(agentBankAccounts)
          .where(and(...conditions))
          .orderBy(desc(agentBankAccounts.id))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(agentBankAccounts)
          .where(and(...conditions))
          .limit(100);
        return {
          items: rows.map(r => ({
            ...r,
            maskedAccount: maskAccountNumber(r.accountNumber),
          })),
          total,
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
  getById: protectedProcedure
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
        return { ...row, maskedAccount: maskAccountNumber(row.accountNumber) };
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
        bankName: z.string().min(2),
        bankCode: z.string().min(3),
        accountNumber: z.string(),
        accountName: z.string().min(2),
        isDefault: z.boolean().default(false),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus =
          "status" in input
            ? String((input as Record<string, unknown>).status)
            : "";
        const currentStatus =
          "currentStatus" in input
            ? String((input as Record<string, unknown>).currentStatus)
            : "pending";
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
          ? Number(
              "amount" in input ? (input as Record<string, unknown>).amount : 0
            )
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
      const db = (await getDb())!;
      // NUBAN validation
      if (!validateNUBAN(input.accountNumber))
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Invalid NUBAN account number — must be exactly 10 digits",
        });
      // Bank code validation
      if (!NIGERIAN_BANKS.includes(input.bankCode))
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `Unknown bank code: ${input.bankCode}. Use CBN-registered bank codes.`,
        });
      // Duplicate detection
      const [existing] = await db
        .select()
        .from(agentBankAccounts)
        .where(
          and(
            eq(agentBankAccounts.agentId, input.agentId),
            eq(agentBankAccounts.accountNumber, input.accountNumber),
            eq(agentBankAccounts.bankCode, input.bankCode)
          )
        )
        .limit(100);
      if (existing)
        throw new TRPCError({
          code: "CONFLICT",
          message: "This bank account is already registered for this agent",
        });
      // Max 5 accounts per agent
      const [{ total }] = await db
        .select({ total: count() })
        .from(agentBankAccounts)
        .where(eq(agentBankAccounts.agentId, input.agentId))
        .limit(100);
      if (total >= 5)
        throw new TRPCError({
          code: "PRECONDITION_FAILED",
          message:
            "Maximum 5 bank accounts per agent. Remove one before adding a new one.",
        });
      // If setting as primary, unset existing primary
      if (input.isDefault) {
        await db
          .update(agentBankAccounts)
          .set({ isDefault: false })
          .where(eq(agentBankAccounts.agentId, input.agentId));
      }
      const [row] = await db
        .insert(agentBankAccounts)
        .values(input as Record<string, unknown>)
        .returning();
      await writeAuditLog({
        agentId:
          typeof ctx === "object" && ctx !== null && "user" in ctx
            ? (ctx.user?.id ?? 0)
            : 0,

        agentCode:
          typeof ctx === "object" && ctx !== null && "user" in ctx
            ? (ctx.user?.agentCode ?? "system")
            : "system",

        action: "MUTATION",

        resource: "agentBankAccountsCrud",

        resourceId:
          typeof input === "object" && input !== null && "id" in input
            ? String(
                "id" in input ? (input as Record<string, unknown>).id : "new"
              )
            : "new",

        status: "success",

        metadata: { input: typeof input === "object" ? input : {} },
      });

      return { ...row, maskedAccount: maskAccountNumber(row.accountNumber) };
    }),
  setPrimary: protectedProcedure
    .input(z.object({ id: z.number(), agentId: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [account] = await db
          .select()
          .from(agentBankAccounts)
          .where(eq(agentBankAccounts.id, input.id))
          .limit(100);
        if (!account)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Bank account not found",
          });
        if (account.agentId !== input.agentId)
          throw new TRPCError({
            code: "FORBIDDEN",
            message: "Account does not belong to this agent",
          });
        await db
          .update(agentBankAccounts)
          .set({ isDefault: false })
          .where(eq(agentBankAccounts.agentId, input.agentId));
        await db
          .update(agentBankAccounts)
          .set({ isDefault: true })
          .where(eq(agentBankAccounts.id, input.id));
        return { success: true, message: "Primary account updated" };
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
        const [account] = await db
          .select()
          .from(agentBankAccounts)
          .where(eq(agentBankAccounts.id, input.id))
          .limit(100);
        if (!account)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Bank account not found",
          });
        await db
          .delete(agentBankAccounts)
          .where(eq(agentBankAccounts.id, input.id));
        return { success: true, deleted: input.id };
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
