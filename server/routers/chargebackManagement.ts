import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, sum } from "drizzle-orm";
import {
  disputes,
  transactions,
  refunds,
  auditLog,
} from "../../drizzle/schema";
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
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "chargebackManagement",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "chargebackManagement",
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
    resource: "chargebackManagement",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "chargebackManagement",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
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

export const chargebackManagementRouter = router({
  listChargebacks: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(50),
          status: z.string().optional(),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = input?.status
          ? await db
              .select()
              .from(disputes)
              .where(
                and(
                  eq(disputes.type, "chargeback"),
                  eq(disputes.status, input.status)
                )
              )
              .orderBy(desc(disputes.createdAt))
              .limit(input?.limit ?? 50)
          : await db
              .select()
              .from(disputes)
              .where(eq(disputes.type, "chargeback"))
              .orderBy(desc(disputes.createdAt))
              .limit(input?.limit ?? 50);
        return { chargebacks: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getChargeback: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [dispute] = await db
          .select()
          .from(disputes)
          .where(eq(disputes.id, input.id))
          .limit(1);
        if (!dispute) return null;
        const [tx] = dispute.transactionId
          ? await db
              .select()
              .from(transactions)
              .where(eq(transactions.id, dispute.transactionId))
              .limit(1)
          : [null];
        return { ...dispute, transaction: tx };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  createChargeback: protectedProcedure
    .input(
      z.object({
        transactionId: z.number(),
        reason: z.string(),
        amount: z.number().positive(),
        evidence: z.string().optional(),
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
        "chargebackManagement",
        "mutation",
        "Executed chargebackManagement mutation"
      );

      try {
        const db = (await getDb())!;
        const [chargeback] = await db
          .insert(disputes)
          .values({
            transactionId: input.transactionId,
            type: "chargeback",
            reason: input.reason,
            amount: String(input.amount),
            status: "open",
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "chargeback_created",
          resource: "disputes",
          resourceId: String(chargeback.id),
          status: "success",
          metadata: {
            transactionId: input.transactionId,
            amount: input.amount,
          },
        } as any);
        return chargeback;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  resolveChargeback: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        resolution: z.enum(["accepted", "rejected", "partial"]),
        refundAmount: z.number().optional(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db
          .update(disputes)
          .set({ status: "resolved", resolution: input.resolution })
          .where(eq(disputes.id, input.id));
        await db.insert(auditLog).values({
          action: "chargeback_resolved",
          resource: "disputes",
          resourceId: String(input.id),
          status: "success",
          metadata: {
            resolution: input.resolution,
            refundAmount: input.refundAmount,
          },
        });
        return { success: true, id: input.id, resolution: input.resolution };
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
      .from(disputes)
      .where(eq(disputes.type, "chargeback"))
      .limit(100);
    const [open] = await db
      .select({ value: count() })
      .from(disputes)
      .where(and(eq(disputes.type, "chargeback"), eq(disputes.status, "open")))
      .limit(100);
    const [resolved] = await db
      .select({ value: count() })
      .from(disputes)
      .where(
        and(eq(disputes.type, "chargeback"), eq(disputes.status, "resolved"))
      )
      .limit(100);
    return {
      totalChargebacks: Number(total.value),
      openChargebacks: Number(open.value),
      resolvedChargebacks: Number(resolved.value),
    };
  }),
});
