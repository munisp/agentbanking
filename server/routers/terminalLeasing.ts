/**
 * Terminal Leasing — manage POS terminal lease agreements, billing cycles,
 * insurance, payment tracking, and return processing.
 *
 * Middleware: Temporal (billing workflow), Kafka (lease events),
 * PostgreSQL (lease records via terminalLeases table), TigerBeetle (billing ledger)
 */
import { z } from "zod";
import crypto from "crypto";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { terminalLeases, posTerminals, agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte, lte, count } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
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

import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce as fluvioPublish } from "../fluvio";
import { dapr } from "../middleware/middlewareConnectors";
import { ingestToLakehouse as lakehouseIngest } from "../lakehouse";
import { cacheGet, cacheSet, cacheInvalidate } from "../lib/cacheClient";

function publishPosMiddleware(
  eventType: string,
  key: string,
  payload: Record<string, unknown>
) {
  publishEvent("pos.terminal.leasing", key, { eventType, ...payload });
  fluvioPublish("pos.terminal.leasing", {
    key: "pos",
    value: JSON.stringify({
      eventType,
      ...payload,
      timestamp: new Date().toISOString(),
    }),
  }).catch(() => {});
  dapr
    .publishEvent("pubsub", "pos.lease.payment.completed", {
      eventType,
      ...payload,
    })
    .catch(() => {});
  lakehouseIngest("pos_terminal_leases", {
    event_type: eventType,
    ...payload,
    source: "terminalLeasing",
  }).catch(() => {});
}

const STATUS_TRANSITIONS: Record<string, string[]> = {
  active: ["suspended", "terminated", "completed"],
  suspended: ["active", "terminated"],
  terminated: [],
  completed: [],
  overdue: ["active", "terminated"],
};

async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "terminalLeasing",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "terminalLeasing",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

function logOperation(action: string, details: Record<string, unknown>) {
  auditFinancialAction(
    "UPDATE",
    "terminalLeasing",
    action,
    JSON.stringify(details).slice(0, 200)
  );
}

export const terminalLeasingRouter = router({
  createLease: protectedProcedure
    .input(
      z.object({
        terminalId: z.number().min(1),
        agentId: z.number().min(1),
        leaseType: z
          .enum(["standard", "premium", "rent_to_own"])
          .default("standard"),
        monthlyRate: z.number().positive().min(100),
        durationMonths: z.number().int().min(1).max(60),
        depositAmount: z.number().min(0).default(0),
        includeInsurance: z.boolean().default(false),
        paymentDay: z.number().int().min(1).max(28).default(1),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [terminal] = await db
          .select()
          .from(posTerminals)
          .where(eq(posTerminals.id, input.terminalId))
          .limit(1);
        if (!terminal)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Terminal not found",
          });

        const [agent] = await db
          .select()
          .from(agents)
          .where(eq(agents.id, input.agentId))
          .limit(1);
        if (!agent)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Agent not found",
          });

        const existingLease = await db
          .select()
          .from(terminalLeases)
          .where(
            and(
              eq(terminalLeases.terminalId, input.terminalId),
              eq(terminalLeases.status, "active")
            )
          )
          .limit(1);
        if (existingLease.length > 0)
          throw new TRPCError({
            code: "CONFLICT",
            message: "Terminal already has an active lease",
          });

        const startDate = new Date();
        const endDate = new Date();
        endDate.setMonth(endDate.getMonth() + input.durationMonths);

        const insuranceRate = input.includeInsurance
          ? Math.round(input.monthlyRate * 0.1)
          : 0;

        const nextPaymentDue = new Date();
        nextPaymentDue.setMonth(nextPaymentDue.getMonth() + 1);
        nextPaymentDue.setDate(input.paymentDay);

        const [lease] = await db
          .insert(terminalLeases)
          .values({
            terminalId: input.terminalId,
            agentId: input.agentId,
            leaseType: input.leaseType,
            monthlyRate: input.monthlyRate,
            depositAmount: input.depositAmount,
            insuranceRate,
            startDate,
            endDate,
            status: "active",
            paymentDay: input.paymentDay,
            totalPaid: input.depositAmount,
            missedPayments: 0,
            nextPaymentDue,
          })
          .returning();

        await db
          .update(posTerminals)
          .set({
            agentId: input.agentId,
            status: "active",
            updatedAt: new Date(),
          })
          .where(eq(posTerminals.id, input.terminalId));

        logOperation("lease_created", {
          leaseId: lease.id,
          terminalId: input.terminalId,
          agentId: input.agentId,
          monthlyRate: input.monthlyRate,
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "TERMINAL_LEASE_CREATED",
          resource: "terminal_lease",
          resourceId: String(lease.id),
          status: "success",
          metadata: {
            terminalId: input.terminalId,
            monthlyRate: input.monthlyRate,
            duration: input.durationMonths,
            leaseType: input.leaseType,
          },
        });

        publishPosMiddleware(
          "createLease",
          String(input.terminalId ?? "unknown"),
          { action: "createLease" }
        );

        return {
          success: true,
          message: "Lease created successfully",
          lease,
          totalCost:
            input.monthlyRate * input.durationMonths +
            insuranceRate * input.durationMonths +
            input.depositAmount,
        };
      });
    }),

  listLeases: protectedProcedure
    .input(
      z.object({
        status: z.string().max(32).optional(),
        agentId: z.number().optional(),
        terminalId: z.number().optional(),
        page: z.number().min(1).default(1),
        limit: z.number().min(1).max(100).default(20),
      })
    )
    .query(async ({ input }) => {
      const db = (await getDb())!;
      if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const offset = (input.page - 1) * input.limit;
      const conditions = [];
      if (input.status)
        conditions.push(eq(terminalLeases.status, input.status));
      if (input.agentId)
        conditions.push(eq(terminalLeases.agentId, input.agentId));
      if (input.terminalId)
        conditions.push(eq(terminalLeases.terminalId, input.terminalId));

      const where = conditions.length > 0 ? and(...conditions) : undefined;

      const [items, [{ total }]] = await Promise.all([
        db
          .select()
          .from(terminalLeases)
          .where(where)
          .orderBy(desc(terminalLeases.createdAt))
          .limit(input.limit)
          .offset(offset),
        db.select({ total: count() }).from(terminalLeases).where(where),
      ]);

      return { items, total, page: input.page, limit: input.limit };
    }),

  getLeaseById: protectedProcedure
    .input(z.object({ id: z.number().min(1) }))
    .query(async ({ input }) => {
      const db = (await getDb())!;
      if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [lease] = await db
        .select()
        .from(terminalLeases)
        .where(eq(terminalLeases.id, input.id))
        .limit(1);
      if (!lease) throw new TRPCError({ code: "NOT_FOUND" });

      const monthlyTotal = lease.monthlyRate + lease.insuranceRate;
      const monthsRemaining = Math.max(
        0,
        Math.ceil(
          (new Date(lease.endDate).getTime() - Date.now()) /
            (30 * 24 * 60 * 60 * 1000)
        )
      );
      const remainingBalance = monthlyTotal * monthsRemaining - lease.totalPaid;

      return {
        ...lease,
        monthlyTotal,
        monthsRemaining,
        remainingBalance: Math.max(0, remainingBalance),
      };
    }),

  recordPayment: protectedProcedure
    .input(
      z.object({
        leaseId: z.number().min(1),
        amount: z.number().positive(),
        paymentRef: z.string().min(1).max(128).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [lease] = await db
          .select()
          .from(terminalLeases)
          .where(eq(terminalLeases.id, input.leaseId))
          .limit(1);
        if (!lease) throw new TRPCError({ code: "NOT_FOUND" });
        if (lease.status === "terminated" || lease.status === "completed")
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Cannot record payment for ${lease.status} lease`,
          });

        const newTotalPaid = lease.totalPaid + input.amount;
        const nextDue = new Date(lease.nextPaymentDue || new Date());
        nextDue.setMonth(nextDue.getMonth() + 1);

        const [updated] = await db
          .update(terminalLeases)
          .set({
            totalPaid: newTotalPaid,
            lastPaymentAt: new Date(),
            nextPaymentDue: nextDue,
            missedPayments: Math.max(0, lease.missedPayments - 1),
            status: "active",
            updatedAt: new Date(),
          })
          .where(eq(terminalLeases.id, input.leaseId))
          .returning();

        const leasePaymentRef =
          input.paymentRef ??
          `LEASE-${input.leaseId}-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;

        // TigerBeetle double-entry: agent float (2001) → lease revenue (4001)
        tbCreateTransfer({
          debitAccountId: "2001",
          creditAccountId: "4001",
          amount: Math.round(input.amount * 100),
          ref: leasePaymentRef,
          txType: "lease_payment",
          agentCode: session.agentCode,
        }).catch(() => {});
        fluvioPublish("tx.created", {
          key: session.agentCode,
          value: JSON.stringify({
            txRef: leasePaymentRef,
            agentCode: session.agentCode,
            amount: input.amount,
            type: "lease_payment",
            timestamp: Date.now(),
          }),
        }).catch(() => {});
        lakehouseIngest("lease_payments", {
          ref: leasePaymentRef,
          leaseId: input.leaseId,
          agentId: session.id,
          amount: input.amount,
          totalPaid: newTotalPaid,
          timestamp: new Date().toISOString(),
        }).catch(() => {});

        logOperation("payment_recorded", {
          leaseId: input.leaseId,
          amount: input.amount,
          totalPaid: newTotalPaid,
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "LEASE_PAYMENT_RECORDED",
          resource: "terminal_lease",
          resourceId: String(input.leaseId),
          status: "success",
          metadata: { amount: input.amount, paymentRef: input.paymentRef },
        });

        publishPosMiddleware("recordPayment", String(input.leaseId), {
          action: "recordPayment",
          ...input,
        });
        return {
          success: true,
          message: "Payment recorded",
          lease: updated,
          nextPaymentDue: nextDue.toISOString(),
        };
      });
    }),

  terminateLease: protectedProcedure
    .input(
      z.object({
        leaseId: z.number().min(1),
        reason: z.string().min(1).max(256),
        returnCondition: z
          .enum(["good", "fair", "poor", "damaged", "missing"])
          .optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return executeInTransaction(async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [lease] = await db
          .select()
          .from(terminalLeases)
          .where(eq(terminalLeases.id, input.leaseId))
          .limit(1);
        if (!lease) throw new TRPCError({ code: "NOT_FOUND" });

        const allowed = STATUS_TRANSITIONS[lease.status] ?? [];
        if (!allowed.includes("terminated"))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Cannot terminate lease in '${lease.status}' status`,
          });

        const latePenalty =
          lease.missedPayments > 0
            ? calculateLatePenalty(
                lease.monthlyRate * lease.missedPayments,
                lease.missedPayments
              )
            : { penalty: 0 };

        const [updated] = await db
          .update(terminalLeases)
          .set({
            status: "terminated",
            returnCondition: input.returnCondition,
            returnedAt: input.returnCondition ? new Date() : null,
            notes: input.reason,
            updatedAt: new Date(),
          })
          .where(eq(terminalLeases.id, input.leaseId))
          .returning();

        await db
          .update(posTerminals)
          .set({ status: "unassigned", agentId: null, updatedAt: new Date() })
          .where(eq(posTerminals.id, lease.terminalId));

        logOperation("lease_terminated", {
          leaseId: input.leaseId,
          reason: input.reason,
          latePenalty: latePenalty.penalty,
        });

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "TERMINAL_LEASE_TERMINATED",
          resource: "terminal_lease",
          resourceId: String(input.leaseId),
          status: "success",
          metadata: {
            reason: input.reason,
            returnCondition: input.returnCondition,
            latePenalty: latePenalty.penalty,
          },
        });

        publishPosMiddleware("terminateLease", String(input.leaseId), {
          action: "terminateLease",
          ...input,
        });
        return {
          success: true,
          message: "Lease terminated",
          lease: updated,
          latePenalty: latePenalty.penalty,
        };
      });
    }),

  leaseStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

    const [totals] = await db
      .select({
        total: count(),
        totalRevenue: sql<number>`COALESCE(SUM(${terminalLeases.totalPaid}), 0)`,
      })
      .from(terminalLeases);

    const byStatus = await db
      .select({
        status: terminalLeases.status,
        cnt: count(),
      })
      .from(terminalLeases)
      .groupBy(terminalLeases.status);

    const overdue = await db
      .select({ cnt: count() })
      .from(terminalLeases)
      .where(
        and(
          eq(terminalLeases.status, "active"),
          lte(terminalLeases.nextPaymentDue, sql`NOW()`)
        )
      );

    return {
      totalLeases: Number(totals?.total ?? 0),
      totalRevenue: Number(totals?.totalRevenue ?? 0),
      byStatus: Object.fromEntries(
        byStatus.map((r: { status: string; cnt: number }) => [
          r.status,
          Number(r.cnt),
        ])
      ),
      overdueCount: Number(overdue[0]?.cnt ?? 0),
    };
  }),
});
