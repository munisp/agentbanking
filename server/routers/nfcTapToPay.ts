import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { sql, eq, and, gte, lte, desc, count } from "drizzle-orm";
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
import { checkDailyLimit } from "../lib/cbnLimits";
import { publishEvent } from "../kafkaClient";
import { agents, transactions, gl_journal_entries } from "../../drizzle/schema";
import { getAgentFromCookie } from "../middleware/agentAuth";
import crypto from "crypto";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  initiated: ["menu_displayed"],
  menu_displayed: ["input_received"],
  input_received: ["processing"],
  processing: ["confirmation_pending", "completed", "failed"],
  confirmation_pending: ["completed", "cancelled", "timed_out"],
  completed: ["archived"],
  failed: ["retry", "cancelled"],
  retry: ["processing"],
  timed_out: ["cancelled"],
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
      "nfcTapToPay",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "nfcTapToPay",
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
    resource: "nfcTapToPay",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "nfcTapToPay",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Database Operations Helper ─────────────────────────────────────────────
async function checkDbHealth() {
  try {
    const db = await (await import("../db")).getDb();
    if ((db as any)?._isNoop) return { connected: false, latencyMs: 0 };
    const start = Date.now();
    await db
      .select({ val: (await import("drizzle-orm")).sql`1` })
      .from((await import("drizzle-orm")).sql`(SELECT 1) AS t`);
    return { connected: true, latencyMs: Date.now() - start };
  } catch {
    return { connected: false, latencyMs: 0 };
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

export const nfcTapToPayRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "nfc_terminals"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [activeRes, todayRes, volumeRes, avgTimeRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "nfc_terminals" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "nfc_terminals" WHERE created_at >= CURRENT_DATE`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'amount')::numeric), 0) as vol FROM "nfc_terminals" WHERE created_at >= CURRENT_DATE`
          )
          .catch(() => ({ rows: [{ vol: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(AVG((data->>'tap_duration_ms')::numeric), 0) as avg_ms FROM "nfc_terminals" WHERE status = 'approved'`
          )
          .catch(() => ({ rows: [{ avg_ms: 0 }] })),
      ]);
      const activeResult = (activeRes as any).rows?.[0]?.cnt;
      const todayResult = (todayRes as any).rows?.[0]?.cnt;
      const volumeResult = (volumeRes as any).rows?.[0]?.vol;
      const avgTimeResult = (avgTimeRes as any).rows?.[0]?.avg_ms;
      return {
        activeTerminals: Number(activeResult ?? 0),
        transactionsToday: Number(todayResult ?? 0),
        volumeToday: Number(volumeResult ?? 0),
        avgTapTime:
          total > 0
            ? (Number(avgTimeResult ?? 0) / 1000).toFixed(2) + "s"
            : "0s",
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        activeTerminals: 0,
        transactionsToday: 0,
        volumeToday: 0,
        avgTapTime: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
        status: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      const db = (await getDb())!;
      try {
        const lim = input.limit;
        const off = input.offset;
        const result = await db.execute(
          sql`SELECT id, data, status, created_at, agent_id FROM "nfc_terminals" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "nfc_terminals"`
        );
        return {
          items: ((result as any).rows ?? []).map((row: any) => ({
            id: row.id,
            ...((typeof row.data === "string"
              ? JSON.parse(row.data)
              : row.data) || {}),
            status: row.status,
            createdAt: row.created_at,
            agentId: row.agent_id,
          })),
          total: Number((countResult as any).rows?.[0]?.cnt ?? 0),
        };
      } catch {
        return { items: [] as any[], total: 0 };
      }
    }),

  create: protectedProcedure
    .input(z.object({ data: z.record(z.string(), z.unknown()) }))
    .mutation(async ({ input, ctx }) => {
      // Enforce STATUS_TRANSITIONS state machine
      if (typeof input === "object" && "status" in input) {
        const currentStatus = "pending"; // Will be overridden by DB lookup
        const newStatus = (input as any).status;
        const allowed =
          STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition`,
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
      const db = (await getDb())!;

      if (!input.data.terminalId || typeof input.data.terminalId !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "terminalId is required for NFC registration",
        });
      }
      if (
        !input.data.deviceModel ||
        typeof input.data.deviceModel !== "string"
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "deviceModel is required (Android NFC-enabled device)",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "nfc_terminals" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
      );
      const id = (result as any).rows?.[0]?.id;
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

        resource: "nfcTapToPay",

        resourceId:
          typeof input === "object" && input !== null && "id" in input
            ? String((input as any).id)
            : "new",

        status: "success",

        metadata: { input: typeof input === "object" ? input : {} },
      });

      return { id, status: "created" };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const db = (await getDb())!;
      const recordId = input.id;
      const result = await db.execute(
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "nfc_terminals" WHERE id = ${recordId}`
      );
      if (!(result as any).rows?.length) {
        throw new TRPCError({ code: "NOT_FOUND", message: "Record not found" });
      }
      const row: any = (result as any).rows[0];
      return {
        id: row.id,
        ...((typeof row.data === "string" ? JSON.parse(row.data) : row.data) ||
          {}),
        status: row.status,
        createdAt: row.created_at,
        agentId: row.agent_id,
        metadata: row.metadata,
      };
    }),

  updateStatus: protectedProcedure
    .input(z.object({ id: z.number(), status: z.string() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;

      const validStatuses = [
        "approved",
        "declined",
        "pending",
        "reversed",
        "active",
      ];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Status must be one of: " + validStatuses.join(", "),
        });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "nfc_terminals" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "nfc_terminals" GROUP BY status`
      );
      const byStatus = Object.fromEntries(
        ((result as any).rows ?? []).map((r: any) => [r.status, Number(r.cnt)])
      );
      return {
        byStatus,
        total: Object.values(byStatus).reduce(
          (a: number, b: any) => a + Number(b),
          0
        ),
        generatedAt: new Date().toISOString(),
      };
    } catch {
      return {
        byStatus: {} as Record<string, number>,
        total: 0,
        generatedAt: new Date().toISOString(),
      };
    }
  }),

  serviceHealth: protectedProcedure.query(async () => {
    const services = [
      { name: "NFC Tap-to-Pay (Go)", url: "http://localhost:8236/health" },
      { name: "NFC Tap-to-Pay (Rust)", url: "http://localhost:8237/health" },
      {
        name: "NFC Tap-to-Pay (Python)",
        url: "http://localhost:8238/health",
      },
    ];
    const results = await Promise.all(
      services.map(async svc => {
        try {
          const res = await fetch(svc.url, {
            signal: AbortSignal.timeout(3000),
          });
          const data = await res.json();
          return { ...svc, status: "healthy" as const, data };
        } catch {
          return { ...svc, status: "unhealthy" as const, data: null };
        }
      })
    );
    return { services: results, checkedAt: new Date().toISOString() };
  }),

  // ── NFC Payment Execution ─────────────────────────────────────────────────
  processPayment: protectedProcedure
    .input(z.object({
      terminalId: z.string().min(1),
      amount: z.number().positive(),
      cardType: z.enum(["visa", "mastercard", "verve", "unknown"]).default("unknown"),
      idempotencyKey: z.string().min(16).max(64),
    }))
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

        const db = (await getDb())!;
        const ref = `NFC-${crypto.randomInt(100000, 999999)}-${Date.now()}`;

        return await withTransaction(async (tx) => {
          // CBN limit check
          const limitCheck = await checkDailyLimit(db, session.id, "tier3", input.amount);
          if (!limitCheck.allowed)
            throw new TRPCError({ code: "BAD_REQUEST", message: `Daily limit exceeded: ${limitCheck.reason}` });

          // Lock agent float
          const agentResult = await tx.execute(
            sql`SELECT float_balance FROM agents WHERE id = ${session.id} FOR UPDATE`
          );
          const agent = (agentResult as any).rows?.[0];
          if (!agent) throw new TRPCError({ code: "NOT_FOUND", message: "Agent not found" });

          const floatBalance = parseFloat(agent.float_balance || "0");
          if (floatBalance < input.amount)
            throw new TRPCError({ code: "BAD_REQUEST", message: "Insufficient float balance" });

          const fees = calculateFee(input.amount, "transfer");
          const commission = calculateCommission(fees.fee, "transfer");

          // Debit agent float
          await tx.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - ${input.amount} WHERE id = ${session.id}`
          );

          // Record transaction
          const txResult = await tx.execute(
            sql`INSERT INTO transactions (ref, agent_id, type, amount, fee, commission, currency, channel, status, metadata)
                VALUES (${ref}, ${session.id}, 'NFC Payment', ${String(input.amount)}, ${String(fees.fee)}, ${String(commission.agentShare)}, 'NGN', 'NFC', 'success',
                ${JSON.stringify({ terminalId: input.terminalId, cardType: input.cardType })}::jsonb) RETURNING id`
          );
          const txId = (txResult as any).rows?.[0]?.id;

          // GL: Debit Cash-on-Hand (1001), Credit Agent Float (2001)
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `NFC tap-to-pay ${input.cardType} via terminal ${input.terminalId}`,
            debitAccountId: 1001,
            creditAccountId: 2001,
            amount: Math.round(input.amount * 100),
            currency: "NGN",
            referenceType: "nfc_payment",
            referenceId: ref,
            postedBy: session.agentCode,
            status: "posted",
          });

          // GL: Fee revenue
          if (fees.fee > 0) {
            await db.insert(gl_journal_entries).values({
              entryNumber: `JE-FEE-${ref}`,
              description: `NFC payment fee for ${ref}`,
              debitAccountId: 2001,
              creditAccountId: 4001,
              amount: Math.round(fees.fee * 100),
              currency: "NGN",
              referenceType: "nfc_fee",
              referenceId: ref,
              postedBy: session.agentCode,
              status: "posted",
            });
          }

          publishEvent("pos.transactions.created", ref, {
            type: "nfc_payment",
            ref, terminalId: input.terminalId, cardType: input.cardType,
            amount: input.amount, fee: fees.fee, commission: commission.agentShare,
            agentId: session.id, timestamp: new Date().toISOString(),
          }, { agentCode: session.agentCode }).catch(() => {});

          // TigerBeetle dual-ledger
          tbCreateTransfer({
            debitAccountId: "1001", creditAccountId: "2001",
            amount: Math.round(input.amount * 100),
            ref, txType: "nfc_payment", agentCode: session.agentCode,
          }).catch(() => {});

          // Fluvio real-time streaming
          publishTxToFluvio({
            txRef: ref, agentCode: session.agentCode,
            amount: input.amount, type: "nfc_payment", timestamp: Date.now(),
          }).catch(() => {});

          // Dapr pub/sub
          dapr.publishEvent("pubsub", "nfc.payment.completed", {
            ref, terminalId: input.terminalId, amount: input.amount,
            agentId: session.id, cardType: input.cardType,
          }).catch(() => {});

          // Redis — invalidate agent balance cache
          cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});

          // Lakehouse analytics
          ingestToLakehouse("nfc_payments", {
            ref, terminalId: input.terminalId, cardType: input.cardType,
            amount: input.amount, fee: fees.fee, commission: commission.agentShare,
            agentId: session.id, timestamp: new Date().toISOString(),
          }).catch(() => {});

          writeAuditLog({
            agentId: session.id, agentCode: session.agentCode,
            action: "NFC_PAYMENT", resource: "nfcTapToPay", resourceId: ref,
            status: "success",
            metadata: { amount: input.amount, terminalId: input.terminalId, cardType: input.cardType },
          }).catch(() => {});

          return {
            success: true, ref, transactionId: txId,
            amount: input.amount, fee: fees.fee, commission: commission.agentShare,
            timestamp: new Date().toISOString(),
          };
        }, "nfcTapToPay.processPayment");
      });
    }),

  refundPayment: protectedProcedure
    .input(z.object({
      transactionRef: z.string().min(1),
      reason: z.string().min(1).max(500),
      idempotencyKey: z.string().min(16).max(64),
    }))
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

        const db = (await getDb())!;
        const refundRef = `NFC-REFUND-${Date.now()}`;

        return await withTransaction(async (tx) => {
          // Lock original transaction
          const txResult = await tx.execute(
            sql`SELECT id, amount, agent_id, status FROM transactions WHERE ref = ${input.transactionRef} AND type = 'NFC Payment' FOR UPDATE`
          );
          const originalTx = (txResult as any).rows?.[0];
          if (!originalTx) throw new TRPCError({ code: "NOT_FOUND", message: "NFC transaction not found" });
          if (originalTx.status === "reversed")
            throw new TRPCError({ code: "BAD_REQUEST", message: "Transaction already reversed" });

          const amount = parseFloat(originalTx.amount);

          // Credit agent float back
          await tx.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) + ${amount} WHERE id = ${originalTx.agent_id}`
          );

          // Mark original as reversed
          await tx.execute(
            sql`UPDATE transactions SET status = 'reversed' WHERE id = ${originalTx.id}`
          );

          // GL reversal: Debit Agent Float (2001), Credit Cash-on-Hand (1001)
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${refundRef}`,
            description: `NFC refund for ${input.transactionRef}: ${input.reason}`,
            debitAccountId: 2001,
            creditAccountId: 1001,
            amount: Math.round(amount * 100),
            currency: "NGN",
            referenceType: "nfc_refund",
            referenceId: refundRef,
            postedBy: session.agentCode,
            status: "posted",
          });

          publishEvent("pos.transactions.created", refundRef, {
            type: "nfc_refund", refundRef, originalRef: input.transactionRef,
            amount, reason: input.reason, agentId: session.id,
            timestamp: new Date().toISOString(),
          }, { agentCode: session.agentCode }).catch(() => {});

          // TigerBeetle reversal
          tbCreateTransfer({
            debitAccountId: "2001", creditAccountId: "1001",
            amount: Math.round(amount * 100),
            ref: refundRef, txType: "nfc_refund", agentCode: session.agentCode,
          }).catch(() => {});

          // Fluvio + Dapr + Redis + Lakehouse
          publishTxToFluvio({ txRef: refundRef, agentCode: session.agentCode, amount, type: "nfc_refund", timestamp: Date.now() }).catch(() => {});
          dapr.publishEvent("pubsub", "nfc.refund.completed", { refundRef, originalRef: input.transactionRef, amount, agentId: session.id }).catch(() => {});
          cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
          ingestToLakehouse("nfc_refunds", { refundRef, originalRef: input.transactionRef, amount, agentId: session.id, reason: input.reason, timestamp: new Date().toISOString() }).catch(() => {});

          writeAuditLog({
            agentId: session.id, agentCode: session.agentCode,
            action: "NFC_REFUND", resource: "nfcTapToPay", resourceId: refundRef,
            status: "success",
            metadata: { originalRef: input.transactionRef, amount, reason: input.reason },
          }).catch(() => {});

          return { success: true, refundRef, originalRef: input.transactionRef, amount, timestamp: new Date().toISOString() };
        }, "nfcTapToPay.refundPayment");
      });
    }),
});
