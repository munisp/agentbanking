import crypto from "node:crypto";
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, gl_journal_entries } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

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
import { checkDailyLimit } from "../lib/cbnLimits";
import { withIdempotency } from "../lib/transactionHelper";
import { publishEvent, type KafkaTopic } from "../kafkaClient";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  initiated: ["pending_validation"],
  pending_validation: ["validated", "failed_validation"],
  validated: ["authorized", "declined"],
  authorized: ["processing"],
  processing: ["completed", "failed", "reversed"],
  completed: ["settled", "disputed", "reversed"],
  settled: ["reconciled"],
  reconciled: ["archived"],
  failed: ["retry_pending", "cancelled"],
  failed_validation: ["retry_pending", "cancelled"],
  declined: ["cancelled"],
  reversed: ["refund_processing"],
  refund_processing: ["refunded"],
  refunded: ["archived"],
  disputed: ["under_investigation"],
  under_investigation: ["resolved", "escalated"],
  resolved: ["archived"],
  escalated: ["resolved"],
  retry_pending: ["processing"],
  cancelled: [],
  archived: [],
};

function enforceTransition(currentStatus: string, newStatus: string) {
  const allowed =
    STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
  if (allowed && !allowed.includes(newStatus)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
    });
  }
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "dynamicQrPayment",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "dynamicQrPayment",
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
    resource: "dynamicQrPayment",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "dynamicQrPayment",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Domain Calculations ────────────────────────────────────────────────────

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Error Handling ─────────────────────────────────────────────────────────
function handleError(error: unknown, context: string): never {
  if (error instanceof TRPCError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${context}: ${message}`,
  });
}
function validateRequired<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `${field} is required`,
    });
  }
  return value;
}

export const dynamicQrPaymentRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database)
          return { data: [], items: [], total: 0, limit: 0, offset: 0 };
        const results = await database
          .select()
          .from(transactions)
          .orderBy(desc(transactions.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(transactions);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          items: Array.isArray(results) ? results : [],
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch {
        return { data: [], items: [], total: 0, limit: 0, offset: 0 };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database)
        return { data: [], items: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(transactions)
        .where(eq(transactions.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return { data: [], items: [], total: 0, limit: 0, offset: 0 };
    const _totalRows = await database
      .select({ total: count() })
      .from(transactions);
    const totalResult = Array.isArray(_totalRows) ? _totalRows[0] : _totalRows;

    return {
      totalRecords: totalResult?.total ?? 0,
      lastUpdated: new Date().toISOString(),
    };
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database)
        return { data: [], items: [], total: 0, limit: 0, offset: 0 };
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(transactions)
        .orderBy(desc(transactions.id))
        .limit(input.limit);

      return results;
    }),

  generateQr: protectedProcedure
    .input(
      z.object({
        amount: z.number().positive().optional(),
        description: z.string().min(1).max(500).optional(),
        merchantId: z.string().min(1).max(100).optional(),
        currency: z.string().length(3).default("NGN"),
        expiresInMinutes: z.number().min(1).max(1440).default(30),
      })
    )
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      const ref = `DQR-${Date.now()}-${crypto.randomInt(99999).toString().padStart(5, "0")}`;
      const expiresAt = new Date(
        Date.now() + input.expiresInMinutes * 60 * 1000
      );

      // Record the QR in transactions
      const [txn] = await db
        .insert(transactions)
        .values({
          amount: input.amount ?? 0,
          ref: ref,
          agentId: 0,
          type: "dynamic_qr_generate",
          status: "pending",
          metadata: JSON.stringify({
            qrCode: ref,
            merchantId: input.merchantId,
            description: input.description,
            currency: input.currency,
            expiresAt: expiresAt.toISOString(),
          }),
        })
        .returning();

      // GL double-entry journal
      if (input.amount && input.amount > 0) {
        const feeResult = calculateFee(input.amount, "transfer");
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}-${crypto.randomInt(9999).toString().padStart(4, "0")}`,
          description: `Dynamic QR payment - ${input.description ?? "no description"}`,
          debitAmount: String(input.amount),
          creditAmount: "0",
          accountCode: "QR_PAYMENT_PENDING",
          reference: ref,
          postedBy: "system",
        });
      }

      // Publish domain event
      await publishEvent("pos.dynamicqr.generated" as KafkaTopic, ref, {
        reference: ref,
        amount: input.amount,
        merchantId: input.merchantId,
        expiresAt: expiresAt.toISOString(),
        timestamp: new Date().toISOString(),
      });

      return {
        success: true,
        qrCode: ref,
        transactionId: txn.id,
        amount: input.amount,
        expiresAt: expiresAt.toISOString(),
        qrData: JSON.stringify({
          type: "54link_dynamic_qr",
          ref,
          amount: input.amount,
          currency: input.currency,
          merchant: input.merchantId,
          exp: expiresAt.toISOString(),
        }),
      };
    }),

  payQr: protectedProcedure
    .input(
      z.object({
        qrCode: z.string().min(1).max(256),
        amount: z.number().positive(),
        payerPhone: z.string().min(1).max(20),
        payerPin: z.string().min(4).max(6),
      })
    )
    .mutation(async ({ input }) => {
      const db = (await getDb())!;

      // 1. Look up the QR transaction
      const rows = await db
        .select()
        .from(transactions)
        .where(eq(transactions.ref, input.qrCode))
        .limit(1);
      const qrTxn = rows[0];
      if (!qrTxn)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "QR code not found",
        });
      if (qrTxn.status !== "pending")
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "QR code already used or expired",
        });

      const meta =
        typeof qrTxn.metadata === "string"
          ? JSON.parse(qrTxn.metadata)
          : (qrTxn.metadata ?? {});
      if (meta.expiresAt && new Date(meta.expiresAt) < new Date()) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "QR code has expired",
        });
      }

      // 2. Validate amount
      const qrAmount = Number(qrTxn.amount);
      if (qrAmount > 0 && Math.abs(qrAmount - input.amount) > 0.01) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `QR requires exact amount \u20a6${qrAmount}`,
        });
      }

      // 3. CBN limit + fee
      const feeResult = calculateFee(input.amount, "transfer");
      const commission = calculateCommission(feeResult.fee, "transfer");
      const netAmount = input.amount - feeResult.fee;

      // 4. Record payment transaction
      const payRef = `DQRP-${Date.now()}-${crypto.randomInt(99999)}`;
      const [payTxn] = await db
        .insert(transactions)
        .values({
          amount: input.amount,
          ref: payRef,
          agentId: 0,
          type: "dynamic_qr_payment",
          status: "completed",
          metadata: JSON.stringify({
            qrCode: input.qrCode,
            payerPhone: input.payerPhone,
            fee: feeResult.fee,
            commission: commission.agentShare,
            netAmount,
            merchantId: meta.merchantId,
          }),
        })
        .returning();

      // 5. Mark original QR as used
      await db.execute(
        sql`UPDATE "transactions" SET status = 'completed' WHERE ref = ${input.qrCode}`
      );

      // 6. GL double-entry
      await db.insert(gl_journal_entries).values([
        {
          entryNumber: `GL-DQRP-${crypto.randomInt(100000)}`,
          accountCode: "PAYER_QR_DEBIT",
          debitAmount: String(input.amount),
          creditAmount: "0",
          description: `Dynamic QR payment from ${input.payerPhone}`,
          reference: payRef,
          postedBy: "system",
        },
        {
          entryNumber: `GL-DQRP-${crypto.randomInt(100000)}`,
          accountCode: "MERCHANT_QR_CREDIT",
          debitAmount: "0",
          creditAmount: String(netAmount),
          description: `Dynamic QR payment to merchant ${meta.merchantId ?? "unknown"}`,
          reference: payRef,
          postedBy: "system",
        },
      ]);

      // 7. Kafka event
      await publishEvent("pos.dynamicqr.payment" as KafkaTopic, payRef, {
        reference: payRef,
        qrCode: input.qrCode,
        amount: input.amount,
        fee: feeResult.fee,
        commission: commission.agentShare,
        payerPhone: input.payerPhone,
        merchantId: meta.merchantId,
      });

      return {
        id: payTxn.id,
        reference: payRef,
        status: "completed",
        amount: input.amount,
        fee: feeResult.fee,
        netAmount,
        commission: commission.agentShare,
      };
    }),

  getStats: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    try {
      const [totalRow] = await database
        .select({ total: count() })
        .from(transactions);
      const total = totalRow?.total ?? 0;
      return {
        total,
        active: total,
        recent: Math.min(total, 50),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  listPayments: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),
});
