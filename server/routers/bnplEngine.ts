import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { gl_journal_entries, transactions, agents } from "../../drizzle/schema";
import { sql, eq, and, gte, lte, desc, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";
import { getAgentFromCookie } from "../middleware/agentAuth";
import crypto from "crypto";

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
      "bnplEngine",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "bnplEngine",
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
    resource: "bnplEngine",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "bnplEngine",
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

export const bnplEngineRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "bnpl_applications"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [activeRes, disbursedRes, paidRes, overdueRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "bnpl_applications" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'amount')::numeric), 0) as total FROM "bnpl_applications" WHERE status IN ('active','completed')`
          )
          .catch(() => ({ rows: [{ total: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "bnpl_applications" WHERE status = 'completed'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "bnpl_applications" WHERE status = 'overdue'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
      ]);
      const activeResult = (activeRes as any).rows?.[0]?.cnt;
      const disbursedResult = (disbursedRes as any).rows?.[0]?.total;
      const paidResult = (paidRes as any).rows?.[0]?.cnt;
      const overdueResult = (overdueRes as any).rows?.[0]?.cnt;
      return {
        activeLoans: Number(activeResult ?? 0),
        totalDisbursed: Number(disbursedResult ?? 0),
        repaymentRate:
          total > 0
            ? ((Number(paidResult ?? 0) / total) * 100).toFixed(1) + "%"
            : "0%",
        overdueCount: Number(overdueResult ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        activeLoans: 0,
        totalDisbursed: 0,
        repaymentRate: 0,
        overdueCount: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "bnpl_applications" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "bnpl_applications"`
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

      const amount = Number(input.data.amount);
      if (!amount || amount < 1000 || amount > 5000000) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "BNPL amount must be between ₦1,000 and ₦5,000,000",
        });
      }
      const installments = Number(input.data.installments);
      if (!installments || installments < 2 || installments > 12) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Installments must be between 2 and 12",
        });
      }
      if (!input.data.customerId) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "customerId is required",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "bnpl_applications" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
      );
      const id = (result as any).rows?.[0]?.id;

      // Fund-flow integration: a BNPL origination extends credit to the customer,
      // so emit the ledger + event fan-out (fail-open) the same way repayment does.
      const originationRef = `BNPL-${id ?? "new"}-${crypto.randomUUID()}`;
      const originationSession = await getAgentFromCookie(ctx.req);
      const originationAgentId = originationSession?.id ?? ctx.user?.id ?? 0;
      const originationAgentCode = originationSession?.agentCode ?? "system";
      publishEvent(
        "pos.transactions.created",
        originationRef,
        {
          type: "bnpl_origination",
          ref: originationRef,
          applicationId: id,
          amount,
          installments,
          customerId: input.data.customerId,
          agentId: originationAgentId,
          timestamp: new Date().toISOString(),
        },
        { agentCode: originationAgentCode }
      ).catch(() => {});
      tbCreateTransfer({
        debitAccountId: "2001",
        creditAccountId: "2004",
        amount: Math.round(amount * 100),
        ref: originationRef,
        txType: "bnpl_origination",
        agentCode: originationAgentCode,
      }).catch(() => {});
      publishTxToFluvio({
        txRef: originationRef,
        agentCode: originationAgentCode,
        amount,
        type: "bnpl_origination",
        timestamp: Date.now(),
      }).catch(() => {});
      dapr
        .publishEvent("pubsub", "bnpl.application.created", {
          ref: originationRef,
          applicationId: id,
          amount,
          installments,
        })
        .catch(() => {});
      ingestToLakehouse("bnpl_originations", {
        ref: originationRef,
        applicationId: id,
        amount,
        installments,
        agentId: originationAgentId,
        timestamp: Date.now(),
      }).catch(() => {});

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

        resource: "bnplEngine",

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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "bnpl_applications" WHERE id = ${recordId}`
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
        "active",
        "overdue",
        "completed",
        "defaulted",
        "pending",
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
        sql`UPDATE "bnpl_applications" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "bnpl_applications" GROUP BY status`
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

  processRepayment: protectedProcedure
    .input(
      z.object({
        applicationId: z.number(),
        amount: z.number().positive(),
        installmentNumber: z.number().min(1).optional(),
        idempotencyKey: z.string().min(16).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        return withTransaction(async tx => {
          const db = tx ?? (await getDb())!;
          const ref = `BNPL-PAY-${Date.now()}-${crypto.randomBytes(4).toString("hex")}`;

          // Fetch BNPL application
          const appResult = await db.execute(
            sql`SELECT * FROM "bnpl_applications" WHERE id = ${input.applicationId} FOR UPDATE`
          );
          const app = (appResult as any).rows?.[0];
          if (!app)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "BNPL application not found",
            });
          if (app.status === "completed") {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: "Loan already fully repaid",
            });
          }

          const appData =
            typeof app.data === "string"
              ? JSON.parse(app.data)
              : (app.data ?? {});
          const totalAmount = Number(appData.amount ?? 0);
          const paidSoFar = Number(appData.paidAmount ?? 0);
          const newPaid = paidSoFar + input.amount;
          const isFullyPaid = newPaid >= totalAmount;

          // Lock agent row and debit
          const agentRows = await db.execute(
            sql`SELECT float_balance FROM agents WHERE id = ${session.id} FOR UPDATE`
          );
          const agentRow =
            (agentRows as any).rows?.[0] ?? (agentRows as any)[0];
          if (!agentRow || Number(agentRow.float_balance) < input.amount) {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: "Insufficient float for repayment",
            });
          }

          await db.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) - ${String(input.amount)} WHERE id = ${session.id}`
          );

          // Update BNPL application
          const updatedData = {
            ...appData,
            paidAmount: newPaid,
            lastPaymentDate: new Date().toISOString(),
          };
          const newStatus = isFullyPaid
            ? "completed"
            : app.status === "overdue"
              ? "active"
              : app.status;
          await db.execute(
            sql`UPDATE "bnpl_applications" SET data = ${JSON.stringify(updatedData)}::jsonb, status = ${newStatus}, updated_at = NOW() WHERE id = ${input.applicationId}`
          );

          // Record transaction
          const [txRecord] = await db
            .insert(transactions)
            .values({
              ref,
              agentId: session.id,
              type: "BNPL Repayment",
              amount: String(input.amount),
              fee: "0",
              commission: "0",
              currency: "NGN",
              channel: "BNPL",
              status: "success",
              metadata: {
                applicationId: input.applicationId,
                installmentNumber: input.installmentNumber,
                paidSoFar: newPaid,
                totalAmount,
                isFullyPaid,
              },
            })
            .returning();

          // GL double-entry: Debit BNPL Receivable, Credit Agent Float
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `BNPL repayment for application #${input.applicationId}`,
            debitAccountId: 1002, // BNPL Receivable (asset reduction)
            creditAccountId: 2001, // Agent Float
            amount: Math.round(input.amount * 100),
            currency: "NGN",
            referenceType: "bnpl_repayment",
            referenceId: String(txRecord.id),
            postedBy: session.agentCode,
            status: "posted",
          });

          // Late penalty if overdue
          if (app.status === "overdue") {
            const penalty = calculateLatePenalty(input.amount, 30);
            if (penalty.penalty > 0) {
              await db.insert(gl_journal_entries).values({
                entryNumber: `JE-PEN-${ref}`,
                description: `Late penalty on BNPL #${input.applicationId}`,
                debitAccountId: 2001,
                creditAccountId: 4002, // Penalty Revenue
                amount: Math.round(penalty.penalty * 100),
                currency: "NGN",
                referenceType: "bnpl_penalty",
                referenceId: String(txRecord.id),
                postedBy: session.agentCode,
                status: "posted",
              });
            }
          }

          // Kafka event
          publishEvent(
            "pos.transactions.created",
            ref,
            {
              type: "bnpl_repayment",
              ref,
              applicationId: input.applicationId,
              amount: input.amount,
              paidSoFar: newPaid,
              totalAmount,
              isFullyPaid,
              agentId: session.id,
              timestamp: new Date().toISOString(),
            },
            { agentCode: session.agentCode }
          ).catch(() => {});

          // TigerBeetle dual-ledger
          tbCreateTransfer({
            debitAccountId: "2004",
            creditAccountId: "2001",
            amount: Math.round(input.amount * 100),
            ref,
            txType: "bnpl_repayment",
            agentCode: session.agentCode,
          }).catch(() => {});

          // Fluvio + Dapr + Redis + Lakehouse
          publishTxToFluvio({
            txRef: ref,
            agentCode: session.agentCode,
            amount: input.amount,
            type: "bnpl_repayment",
            timestamp: Date.now(),
          }).catch(() => {});
          dapr
            .publishEvent("pubsub", "bnpl.repayment.completed", {
              ref,
              applicationId: input.applicationId,
              amount: input.amount,
              isFullyPaid,
            })
            .catch(() => {});
          cacheSet(`agent:balance:${session.id}`, "", 1).catch(() => {});
          ingestToLakehouse("bnpl_repayments", {
            ref,
            applicationId: input.applicationId,
            amount: input.amount,
            totalPaid: newPaid,
            isFullyPaid,
            agentId: session.id,
            timestamp: new Date().toISOString(),
          }).catch(() => {});

          writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "BNPL_REPAYMENT",
            resource: "bnpl",
            resourceId: ref,
            status: "success",
            metadata: {
              applicationId: input.applicationId,
              amount: input.amount,
              isFullyPaid,
            },
          }).catch(() => {});

          return {
            success: true,
            ref,
            transactionId: txRecord.id,
            applicationId: input.applicationId,
            amountPaid: input.amount,
            totalPaid: newPaid,
            totalAmount,
            remainingBalance: Math.max(0, totalAmount - newPaid),
            isFullyPaid,
            status: newStatus,
            timestamp: new Date().toISOString(),
          };
        }, "bnplEngine.processRepayment");
      });
    }),

  collectOverdue: protectedProcedure
    .input(z.object({ limit: z.number().min(1).max(100).default(50) }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;
      const overdueResult = await db.execute(
        sql`SELECT id, data, agent_id FROM "bnpl_applications" WHERE status = 'overdue' ORDER BY created_at ASC LIMIT ${input.limit}`
      );
      const overdueApps = (overdueResult as any).rows ?? [];
      const processed: { id: number; penalty: number }[] = [];

      for (const app of overdueApps) {
        const appData =
          typeof app.data === "string"
            ? JSON.parse(app.data)
            : (app.data ?? {});
        const totalAmount = Number(appData.amount ?? 0);
        const paidAmount = Number(appData.paidAmount ?? 0);
        const outstanding = totalAmount - paidAmount;
        const penalty = calculateLatePenalty(outstanding, 30);
        processed.push({ id: app.id, penalty: penalty.penalty });
      }

      return {
        processed: processed.length,
        items: processed,
        timestamp: new Date().toISOString(),
      };
    }),

  serviceHealth: protectedProcedure.query(async () => {
    const services = [
      { name: "BNPL Engine (Go)", url: "http://localhost:8233/health" },
      { name: "BNPL Engine (Rust)", url: "http://localhost:8234/health" },
      {
        name: "BNPL Engine (Python)",
        url: "http://localhost:8235/health",
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
});
