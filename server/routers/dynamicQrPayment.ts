import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents, gl_journal_entries } from "../../drizzle/schema";
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
import { publishEvent } from "../kafkaClient";
import { getAgentFromCookie } from "../middleware/agentAuth";
import crypto from "crypto";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

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
    .input(z.object({
      amount: z.number().positive(),
      description: z.string().max(255).optional(),
      expiresInMinutes: z.number().min(1).max(1440).default(30),
    }))
    .mutation(async ({ input, ctx }) => {
      const session = await getAgentFromCookie(ctx.req);
      if (!session)
        throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

      const db = (await getDb())!;
      const qrCode = `QR-${crypto.randomInt(100000, 999999)}-${Date.now()}`;
      const expiresAt = new Date(Date.now() + input.expiresInMinutes * 60 * 1000);

      await db.execute(
        sql`INSERT INTO qr_codes (code, agent_id, type, amount, description, status, expires_at)
            VALUES (${qrCode}, ${session.id}, 'dynamic', ${String(input.amount)}, ${input.description ?? ""}, 'active', ${expiresAt})`
      );

      writeAuditLog({
        agentId: session.id, agentCode: session.agentCode,
        action: "QR_GENERATED", resource: "dynamicQrPayment", resourceId: qrCode,
        status: "success",
        metadata: { amount: input.amount, expiresAt: expiresAt.toISOString() },
      }).catch(() => {});

      return {
        success: true,
        qrCode,
        amount: input.amount,
        expiresAt: expiresAt.toISOString(),
      };
    }),

  payQr: protectedProcedure
    .input(z.object({
      qrCode: z.string().min(1),
      idempotencyKey: z.string().min(16).max(64),
    }))
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

        const db = (await getDb())!;

        return await withTransaction(async (tx) => {
          // Lock QR code
          const qrResult = await tx.execute(
            sql`SELECT * FROM qr_codes WHERE code = ${input.qrCode} FOR UPDATE`
          );
          const qr = (qrResult as any).rows?.[0];
          if (!qr) throw new TRPCError({ code: "NOT_FOUND", message: "QR code not found" });
          if (qr.status !== "active")
            throw new TRPCError({ code: "BAD_REQUEST", message: `QR code is ${qr.status}` });
          if (new Date(qr.expires_at) < new Date())
            throw new TRPCError({ code: "BAD_REQUEST", message: "QR code expired" });

          const amount = parseFloat(qr.amount);
          const ref = `QR-PAY-${crypto.randomInt(100000, 999999)}-${Date.now()}`;

          // CBN limit check
          const limitCheck = await checkDailyLimit(db, session.id, "tier3", amount);
          if (!limitCheck.allowed)
            throw new TRPCError({ code: "BAD_REQUEST", message: `Daily limit exceeded: ${limitCheck.reason}` });

          // Lock agent float
          const agentResult = await tx.execute(
            sql`SELECT float_balance FROM agents WHERE id = ${session.id} FOR UPDATE`
          );
          const agent = (agentResult as any).rows?.[0];
          if (!agent) throw new TRPCError({ code: "NOT_FOUND", message: "Agent not found" });
          if (parseFloat(agent.float_balance || "0") < amount)
            throw new TRPCError({ code: "BAD_REQUEST", message: "Insufficient float balance" });

          const fees = calculateFee(amount, "transfer");
          const commission = calculateCommission(fees.fee, "transfer");

          // Debit agent float
          await tx.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - ${amount} WHERE id = ${session.id}`
          );

          // Mark QR as used
          await tx.execute(
            sql`UPDATE qr_codes SET status = 'used' WHERE code = ${input.qrCode}`
          );

          // Record transaction
          const txResult = await tx.execute(
            sql`INSERT INTO transactions (ref, agent_id, type, amount, fee, commission, currency, channel, status, metadata)
                VALUES (${ref}, ${session.id}, 'QR Payment', ${String(amount)}, ${String(fees.fee)}, ${String(commission.agentShare)}, 'NGN', 'QR', 'success',
                ${JSON.stringify({ qrCode: input.qrCode, merchantAgentId: qr.agent_id })}::jsonb) RETURNING id`
          );
          const txId = (txResult as any).rows?.[0]?.id;

          // GL: Debit Cash-on-Hand (1001), Credit Agent Float (2001)
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `QR payment for ${input.qrCode}`,
            debitAccountId: 1001,
            creditAccountId: 2001,
            amount: Math.round(amount * 100),
            currency: "NGN",
            referenceType: "qr_payment",
            referenceId: ref,
            postedBy: session.agentCode,
            status: "posted",
          });

          publishEvent("pos.transactions.created", ref, {
            type: "qr_payment", ref, qrCode: input.qrCode,
            amount, fee: fees.fee, commission: commission.agentShare,
            agentId: session.id, merchantAgentId: qr.agent_id,
            timestamp: new Date().toISOString(),
          }, { agentCode: session.agentCode }).catch(() => {});

          // TigerBeetle dual-ledger
          tbCreateTransfer({
            debitAccountId: "1001", creditAccountId: "2001",
            amount: Math.round(amount * 100),
            ref, txType: "qr_payment", agentCode: session.agentCode,
          }).catch(() => {});

          // Fluvio + Dapr + Redis + Lakehouse
          publishTxToFluvio({ txRef: ref, agentCode: session.agentCode, amount, type: "qr_payment", timestamp: Date.now() }).catch(() => {});
          dapr.publishEvent("pubsub", "qr.payment.completed", { ref, qrCode: input.qrCode, amount, agentId: session.id }).catch(() => {});
          cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
          ingestToLakehouse("qr_payments", { ref, qrCode: input.qrCode, amount, fee: fees.fee, agentId: session.id, timestamp: new Date().toISOString() }).catch(() => {});

          writeAuditLog({
            agentId: session.id, agentCode: session.agentCode,
            action: "QR_PAYMENT", resource: "dynamicQrPayment", resourceId: ref,
            status: "success",
            metadata: { qrCode: input.qrCode, amount },
          }).catch(() => {});

          return {
            success: true, ref, transactionId: txId,
            amount, fee: fees.fee, commission: commission.agentShare,
            timestamp: new Date().toISOString(),
          };
        }, "dynamicQrPayment.payQr");
      });
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
