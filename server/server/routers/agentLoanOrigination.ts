import crypto from "crypto";
import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agentLoans, agents, transactions, gl_journal_entries } from "../../drizzle/schema";
import { eq, and, sql, desc, count } from "drizzle-orm";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  validateAmount,
  withTransaction,
  withIdempotency,
  validateStatusTransition,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateSimpleInterest,
  calculateLoanRepayment,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const LOAN_STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["submitted"],
  submitted: ["under_review"],
  under_review: ["approved", "rejected", "returned"],
  returned: ["submitted"],
  approved: ["disbursement_pending"],
  disbursement_pending: ["disbursed", "cancelled"],
  disbursed: ["active"],
  active: ["delinquent", "paid_off", "written_off"],
  delinquent: ["active", "written_off", "restructured"],
  restructured: ["active"],
  rejected: [],
  cancelled: [],
  paid_off: [],
  written_off: [],
};

const CREDIT_SCORE_THRESHOLDS = {
  excellent: { min: 750, maxRate: 12, maxTenor: 365 },
  good: { min: 650, maxRate: 18, maxTenor: 180 },
  fair: { min: 500, maxRate: 24, maxTenor: 90 },
  poor: { min: 350, maxRate: 30, maxTenor: 30 },
  unscored: { min: 0, maxRate: 36, maxTenor: 14 },
};

export const agentLoanOriginationRouter = router({
  /** Submit a new loan application */
  applyForLoan: protectedProcedure
    .input(
      z.object({
        amount: z.number().positive().min(5000).max(50_000_000),
        purpose: z.enum(["working_capital", "inventory", "equipment", "expansion", "emergency"]),
        tenorDays: z.number().int().min(7).max(365),
        collateralType: z.enum(["none", "pos_terminal", "inventory", "property", "guarantor"]).optional(),
        collateralValue: z.number().min(0).optional(),
        idempotencyKey: z.string().min(16).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        // Check agent credit score and eligibility
        const [agent] = await db
          .select({
            creditScore: agents.creditScore,
            creditLimit: agents.creditLimit,
            floatBalance: agents.floatBalance,
            tier: agents.tier,
          })
          .from(agents)
          .where(eq(agents.id, session.id))
          .limit(1);

        if (!agent)
          throw new TRPCError({ code: "NOT_FOUND", message: "Agent not found" });

        // Determine credit tier
        const score = agent.creditScore ?? 0;
        let creditTier = "unscored";
        for (const [tier, thresholds] of Object.entries(CREDIT_SCORE_THRESHOLDS)) {
          if (score >= thresholds.min) { creditTier = tier; break; }
        }
        const tierConfig = CREDIT_SCORE_THRESHOLDS[creditTier as keyof typeof CREDIT_SCORE_THRESHOLDS];

        // Validate tenor against credit tier
        if (input.tenorDays > tierConfig.maxTenor)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Credit score ${score} (${creditTier}) allows max ${tierConfig.maxTenor} days tenor`,
          });

        // Check amount against credit limit
        if (input.amount > Number(agent.creditLimit || 0))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Amount exceeds credit limit of \u20A6${Number(agent.creditLimit).toLocaleString()}`,
          });

        // Check for existing active loans
        const [existingLoans] = await db
          .select({ count: count() })
          .from(agentLoans)
          .where(
            and(
              eq(agentLoans.agentId, session.id),
              sql`status IN ('active', 'disbursed', 'delinquent')`
            )
          );

        if ((existingLoans?.count ?? 0) >= 3)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Maximum 3 concurrent active loans allowed",
          });

        // Calculate interest rate and repayment schedule
        const annualRate = tierConfig.maxRate;
        const interestResult = calculateSimpleInterest(input.amount, annualRate, input.tenorDays);
        const repayment = calculateLoanRepayment(input.amount, annualRate, input.tenorDays);
        const processingFee = calculateFee(input.amount, "loanDisbursement");

        const ref = `LN-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;

        // Create loan record
        const [loan] = await db
          .insert(agentLoans)
          .values({
            agentId: session.id,
            loanType: input.purpose,
            principalAmount: String(input.amount),
            interestRate: String(annualRate),
            tenorDays: input.tenorDays,
            totalRepayable: String(repayment.totalPayment),
            status: "pending",
            creditScore: score,
          })
          .returning();

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "LOAN_APPLIED",
          resource: "agent_loan",
          resourceId: ref,
          status: "success",
          metadata: {
            amount: input.amount,
            tenor: input.tenorDays,
            rate: annualRate,
            creditScore: score,
            creditTier,
          },
        });

        return {
          success: true,
          loanId: loan.id,
          ref,
          amount: input.amount,
          interestRate: annualRate,
          tenorDays: input.tenorDays,
          totalRepayable: repayment.totalPayment,
          monthlyInstallment: repayment.monthlyPayment,
          processingFee: processingFee.fee,
          creditScore: score,
          creditTier,
          status: "submitted",
        };
      });
    }),

  /** Approve or reject a loan (admin only) */
  decide: protectedProcedure
    .input(
      z.object({
        loanId: z.number().int().positive(),
        decision: z.enum(["approved", "rejected"]),
        reason: z.string().max(500).optional(),
        approvedAmount: z.number().positive().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const session = await getAgentFromCookie(ctx.req);
      if (!session || session.role !== "admin")
        throw new TRPCError({ code: "FORBIDDEN", message: "Admin access required" });

      const db = (await getDb())!;

      const [loan] = await db
        .select()
        .from(agentLoans)
        .where(eq(agentLoans.id, input.loanId))
        .limit(1);

      if (!loan)
        throw new TRPCError({ code: "NOT_FOUND", message: "Loan not found" });

      // Enforce state machine
      const transition = validateStatusTransition(
        loan.status, input.decision === "approved" ? "approved" : "rejected",
        LOAN_STATUS_TRANSITIONS
      );
      if (!transition.valid)
        throw new TRPCError({ code: "BAD_REQUEST", message: transition.error! });

      await db
        .update(agentLoans)
        .set({
          status: input.decision === "approved" ? "approved" : "rejected",
          approvedBy: input.decision === "approved" ? session.id : null,
          updatedAt: new Date(),
        })
        .where(eq(agentLoans.id, input.loanId));

      await writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: input.decision === "approved" ? "LOAN_APPROVED" : "LOAN_REJECTED",
        resource: "agent_loan",
        resourceId: String(input.loanId),
        status: "success",
        metadata: { decision: input.decision, reason: input.reason },
      });

      return { success: true, loanId: input.loanId, status: input.decision };
    }),

  /** Disburse an approved loan to agent float */
  disburse: protectedProcedure
    .input(
      z.object({
        loanId: z.number().int().positive(),
        idempotencyKey: z.string().min(16).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session || session.role !== "admin")
          throw new TRPCError({ code: "FORBIDDEN", message: "Admin access required" });

        return withTransaction(async (tx) => {
          const db = tx ?? (await getDb())!;

          const [loan] = await db
            .select()
            .from(agentLoans)
            .where(eq(agentLoans.id, input.loanId))
            .limit(1);

          if (!loan)
            throw new TRPCError({ code: "NOT_FOUND", message: "Loan not found" });

          const transition = validateStatusTransition(loan.status, "disbursed", LOAN_STATUS_TRANSITIONS);
          if (!transition.valid)
            throw new TRPCError({ code: "BAD_REQUEST", message: transition.error! });

          const amount = Number(loan.principalAmount);
          const fee = calculateFee(amount, "loanDisbursement");
          const netDisbursement = amount - fee.fee;
          const ref = `LD-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;

          // Credit agent float with loan amount (minus processing fee)
          await db
            .update(agents)
            .set({ floatBalance: sql`CAST(${agents.floatBalance} AS numeric) + ${String(netDisbursement)}` })
            .where(eq(agents.id, loan.agentId));

          // Update loan status
          await db
            .update(agentLoans)
            .set({ status: "disbursed", disbursedAt: new Date(), updatedAt: new Date() })
            .where(eq(agentLoans.id, input.loanId));

          // Record as transaction
          await db.insert(transactions).values({
            ref,
            idempotencyKey: input.idempotencyKey,
            agentId: loan.agentId,
            type: "Transfer",
            amount: String(amount),
            fee: String(fee.fee),
            commission: "0",
            currency: "NGN",
            status: "success",
            channel: "System",
            metadata: { loanId: input.loanId, type: "loan_disbursement" },
          });

          // Double-entry: Debit Loan Receivable, Credit Agent Float
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Loan disbursement #${input.loanId}`,
            debitAccountId: 1200, // Loans Receivable (asset)
            creditAccountId: 2001, // Agent Float (liability)
            amount: Math.round(netDisbursement * 100),
            currency: "NGN",
            referenceType: "loan",
            referenceId: String(input.loanId),
            postedBy: session.agentCode,
            status: "posted",
          });

          await writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "LOAN_DISBURSED",
            resource: "agent_loan",
            resourceId: ref,
            status: "success",
            metadata: { loanId: input.loanId, amount, fee: fee.fee, net: netDisbursement },
          });

          return {
            success: true,
            ref,
            loanId: input.loanId,
            disbursedAmount: netDisbursement,
            processingFee: fee.fee,
            status: "disbursed",
          };
        }, "loan.disburse");
      });
    }),

  /** Record a loan repayment */
  repay: protectedProcedure
    .input(
      z.object({
        loanId: z.number().int().positive(),
        amount: z.number().positive().min(100),
        idempotencyKey: z.string().min(16).max(64),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return withIdempotency(input.idempotencyKey, async () => {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

        return withTransaction(async (tx) => {
          const db = tx ?? (await getDb())!;

          const [loan] = await db
            .select()
            .from(agentLoans)
            .where(and(eq(agentLoans.id, input.loanId), eq(agentLoans.agentId, session.id)))
            .limit(1);

          if (!loan)
            throw new TRPCError({ code: "NOT_FOUND", message: "Loan not found" });
          if (!["active", "delinquent"].includes(loan.status))
            throw new TRPCError({ code: "BAD_REQUEST", message: `Cannot repay loan in '${loan.status}' status` });

          const outstanding = Number(loan.totalRepayable) - Number(loan.amountRepaid ?? 0);
          if (input.amount > outstanding)
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Payment exceeds outstanding balance of \u20A6${outstanding.toLocaleString()}`,
            });

          // Check agent has sufficient float
          const [agent] = await db
            .select({ floatBalance: agents.floatBalance })
            .from(agents)
            .where(eq(agents.id, session.id))
            .limit(1);

          if (Number(agent?.floatBalance ?? 0) < input.amount)
            throw new TRPCError({ code: "BAD_REQUEST", message: "Insufficient float balance for repayment" });

          // Debit agent float
          await db
            .update(agents)
            .set({ floatBalance: sql`CAST(${agents.floatBalance} AS numeric) - ${String(input.amount)}` })
            .where(eq(agents.id, session.id));

          // Update loan — track repaid amount
          const newRepaid = Number(loan.amountRepaid ?? 0) + input.amount;
          const isFullyPaid = newRepaid >= Number(loan.totalRepayable);

          await db
            .update(agentLoans)
            .set({
              amountRepaid: String(newRepaid),
              status: isFullyPaid ? "paid_off" : loan.status === "delinquent" ? "active" : loan.status,
              lastPaymentDate: new Date(),
            })
            .where(eq(agentLoans.id, input.loanId));

          const ref = `LR-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;

          await db.insert(transactions).values({
            ref,
            idempotencyKey: input.idempotencyKey,
            agentId: session.id,
            type: "Transfer",
            amount: String(input.amount),
            fee: "0",
            commission: "0",
            currency: "NGN",
            status: "success",
            channel: "System",
            metadata: { loanId: input.loanId, type: "loan_repayment", isFullyPaid },
          });

          // Double-entry: Debit Agent Float, Credit Loan Receivable
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Loan repayment #${input.loanId}`,
            debitAccountId: 2001, // Agent Float
            creditAccountId: 1200, // Loans Receivable
            amount: Math.round(input.amount * 100),
            currency: "NGN",
            referenceType: "loan_repayment",
            referenceId: String(input.loanId),
            postedBy: session.agentCode,
            status: "posted",
          });

          await writeAuditLog({
            agentId: session.id,
            agentCode: session.agentCode,
            action: "LOAN_REPAYMENT",
            resource: "agent_loan",
            resourceId: ref,
            status: "success",
            metadata: { loanId: input.loanId, amount: input.amount, outstanding: outstanding - input.amount, isFullyPaid },
          });

          return {
            success: true,
            ref,
            amountPaid: input.amount,
            totalRepaid: newRepaid,
            outstanding: outstanding - input.amount,
            isFullyPaid,
            status: isFullyPaid ? "paid_off" : "active",
          };
        }, "loan.repay");
      });
    }),

  /** List agent's loans */
  myLoans: protectedProcedure.query(async ({ ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session)
      throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

    const db = (await getDb())!;
    const loans = await db
      .select()
      .from(agentLoans)
      .where(eq(agentLoans.agentId, session.id))
      .orderBy(desc(agentLoans.createdAt))
      .limit(50);

    return { loans, total: loans.length };
  }),

  /** Get loan details */
  getById: protectedProcedure
    .input(z.object({ loanId: z.number().int().positive() }))
    .query(async ({ input, ctx }) => {
      const session = await getAgentFromCookie(ctx.req);
      if (!session)
        throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

      const db = (await getDb())!;
      const [loan] = await db
        .select()
        .from(agentLoans)
        .where(and(eq(agentLoans.id, input.loanId), eq(agentLoans.agentId, session.id)))
        .limit(1);

      if (!loan)
        throw new TRPCError({ code: "NOT_FOUND", message: "Loan not found" });

      // Calculate penalty if delinquent
      let penalty = null;
      if (loan.status === "defaulted" && loan.disbursedAt) {
        const daysOverdue = Math.floor((Date.now() - new Date(loan.disbursedAt).getTime()) / 86400000) - (loan.tenorDays ?? 0);
        if (daysOverdue > 0) {
          penalty = calculateLatePenalty(Number(loan.totalRepayable) - Number(loan.amountRepaid ?? 0), daysOverdue);
        }
      }

      return { ...loan, penalty };
    }),

  getStats: protectedProcedure.query(async ({ ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session)
      throw new TRPCError({ code: "UNAUTHORIZED", message: "Agent session required" });

    const db = (await getDb())!;
    const [totalLoans] = await db.select({ value: count() }).from(agentLoans).where(eq(agentLoans.agentId, session.id)).limit(100);
    const [activeLoans] = await db.select({ value: count() }).from(agentLoans).where(and(eq(agentLoans.agentId, session.id), eq(agentLoans.status, "disbursed"))).limit(100);
    return {
      totalLoans: Number(totalLoans.value),
      activeLoans: Number(activeLoans.value),
      lastUpdated: new Date().toISOString(),
    };
  }),
});
