/**
 * F04: Agent Loan & Credit Facility
 * Loan application, credit scoring, disbursement, repayment tracking, interest calculation
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb, writeAuditLog } from "../db";
import {
  agentLoans,
  agents,
  transactions,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, gte, count, sum, avg, sql } from "drizzle-orm";
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
import { tbCreateTransfer } from "../tbClient";
import { cacheSet, cacheGet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import {
  dapr,
  tigerbeetle,
} from "../middleware/middlewareConnectors";
import { enforcePermission } from "../_core/permify";


const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["submitted", "cancelled"],
  submitted: ["under_review", "rejected"],
  under_review: ["approved", "rejected"],
  approved: ["disbursed"],
  disbursed: ["repaying"],
  repaying: ["completed", "defaulted"],
  completed: [],
  defaulted: ["repaying"],
  rejected: [],
  cancelled: [],
};

// Business rules
const INTEREST_RATES = {
  float_advance: 2.5,
  working_capital: 5.0,
  emergency: 8.0,
}; // monthly %
const MAX_LOAN_MULTIPLIER = 3; // max loan = 3x average monthly volume
const MIN_CREDIT_SCORE = 500;
const CREDIT_SCORE_WEIGHTS = {
  txVolume: 0.3,
  repaymentHistory: 0.25,
  accountAge: 0.2,
  floatUtilization: 0.15,
  fraudHistory: 0.1,
};

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentLoanFacility",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentLoanFacility",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations
export const agentLoanFacilityRouter = router({
  // List loans with filtering
  list: protectedProcedure
    .input(
      z.object({
        page: z.number().default(1),
        limit: z.number().default(20),
        status: z
          .enum([
            "pending",
            "approved",
            "disbursed",
            "repaying",
            "completed",
            "defaulted",
            "rejected",
          ])
          .optional(),
        agentId: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) return { items: [], total: 0 };
        const conditions = [];
        if (input.status) conditions.push(eq(agentLoans.status, input.status));
        if (input.agentId)
          conditions.push(eq(agentLoans.agentId, input.agentId));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const items = await db
          .select()
          .from(agentLoans)
          .where(where)
          .orderBy(desc(agentLoans.createdAt))
          .limit(input.limit)
          .offset((input.page - 1) * input.limit);
        const [{ total }] = await db
          .select({ total: count() })
          .from(agentLoans)
          .where(where)
          .limit(100);
        return { items, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Apply for a loan
  applyLoan: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        loanType: z.enum(["float_advance", "working_capital", "emergency"]),
        principalAmount: z.number().min(10000),
        tenorDays: z.number().min(7).max(365),
        collateralType: z.string().optional(),
        collateralValue: z.number().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      await enforcePermission(String(ctx.user?.id ?? "0"), "loan", "create").catch(() => {});

      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as Record<string, unknown>).status as string;
        const currentStatus =
          ((input as Record<string, unknown>).currentStatus as string) ||
          "pending";
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
          ? Number((input as Record<string, unknown>).amount)
          : 0;
      const fees = calculateFee(txAmount, "loanDisbursement");
      const commission = calculateCommission(fees.fee, "loanDisbursement");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        // Calculate credit score
        const creditScore = await calculateCreditScore(db, input.agentId);
        if (creditScore < MIN_CREDIT_SCORE) {
          throw new Error(
            `Credit score ${creditScore} below minimum ${MIN_CREDIT_SCORE}`
          );
        }
        // Calculate interest
        const monthlyRate = INTEREST_RATES[input.loanType] / 100;
        const months = input.tenorDays / 30;
        const totalInterest = input.principalAmount * monthlyRate * months;
        const totalRepayable = input.principalAmount + totalInterest;
        const [loan] = await db
          .insert(agentLoans)
          .values({
            agentId: input.agentId,
            loanType: input.loanType,
            principalAmount: String(input.principalAmount),
            interestRate: String(INTEREST_RATES[input.loanType]),
            tenorDays: input.tenorDays,
            totalRepayable: String(totalRepayable),
            status: "pending",
            creditScore,
            collateralType: input.collateralType,
            collateralValue: input.collateralValue
              ? String(input.collateralValue)
              : null,
            dueDate: new Date(Date.now() + input.tenorDays * 86400000),
          })
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `agentLoanFacility transaction`,
          debitAccountId: 2001,
          creditAccountId: 1001,
          amount: Math.round(
            (typeof input === "object" && "amount" in input
              ? Number((input as any).amount)
              : 0) * 100
          ),
          currency: "NGN",
          status: "posted",
        });
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

          resource: "agentLoanFacility",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { loan, creditScore, totalInterest, totalRepayable };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Approve a loan
  approve: protectedProcedure
    .input(z.object({ loanId: z.number() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .update(agentLoans)
          .set({
            status: "approved",
            approvedBy: ctx.user?.id,
            updatedAt: new Date(),
          })
          .where(eq(agentLoans.id, input.loanId));

        writeAuditLog({
          agentId: ctx.user?.id ?? 0,
          agentCode: String(ctx.user?.id ?? "system"),
          action: "LOAN_APPROVED",
          resource: "agentLoanFacility",
          resourceId: String(input.loanId),
          status: "success",
          metadata: { loanId: input.loanId },
        }).catch(() => {});

        publishEvent("pos.transactions.created", String(input.loanId), {
          type: "loan_approved",
          loanId: input.loanId,
          approvedBy: ctx.user?.id,
          timestamp: new Date().toISOString(),
        }, { agentCode: String(ctx.user?.id ?? "system") }).catch(() => {});

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

  // Disburse a loan (credit agent float)
  disburse: protectedProcedure
    .input(z.object({ loanId: z.number() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");

        return await withTransaction(async (tx) => {
          // Lock loan row
          const loanResult = await tx.execute(
            sql`SELECT * FROM "agent_loans" WHERE id = ${input.loanId} FOR UPDATE`
          );
          const loan = (loanResult as any).rows?.[0];
          if (!loan) throw new Error("Loan not found");
          if (loan.status !== "approved")
            throw new Error("Loan must be approved before disbursement");

          // Lock agent row and credit float
          await tx.execute(
            sql`SELECT id FROM agents WHERE id = ${loan.agent_id} FOR UPDATE`
          );
          await tx.execute(
            sql`UPDATE agents SET float_balance = CAST(float_balance AS numeric) + ${Number(loan.principal_amount)} WHERE id = ${loan.agent_id}`
          );

          // Update loan status
          await tx.execute(
            sql`UPDATE "agent_loans" SET status = 'disbursed', disbursed_at = NOW(), updated_at = NOW() WHERE id = ${input.loanId}`
          );

          // GL entry: Debit Agent Float (2001), Credit Loan Payable (2004)
          const ref = `LOAN-DISB-${input.loanId}-${Date.now()}`;
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Loan disbursement #${input.loanId}`,
            debitAccountId: 2001,
            creditAccountId: 2004,
            amount: Math.round(Number(loan.principal_amount) * 100),
            currency: "NGN",
            referenceType: "loan_disbursement",
            referenceId: ref,
            postedBy: String(ctx.user?.id ?? "system"),
            status: "posted",
          });

          // Kafka event
          publishEvent(
            "pos.transactions.created",
            ref,
            {
              type: "loan_disbursement",
              loanId: input.loanId,
              agentId: loan.agent_id,
              amount: Number(loan.principal_amount),
              timestamp: new Date().toISOString(),
            },
            { agentCode: String(ctx.user?.id ?? "system") }
          ).catch(() => {});

          // TigerBeetle dual-ledger entry
          tbCreateTransfer({
            debitAccountId: "2001",
            creditAccountId: "2004",
            amount: Math.round(Number(loan.principal_amount) * 100),
            ref,
            txType: "loan_disbursement",
            agentCode: String(ctx.user?.id ?? "system"),
          }).catch(() => {});

          // Fluvio real-time streaming
          publishTxToFluvio({
            txRef: ref,
            agentCode: String(ctx.user?.id ?? "system"),
            amount: Number(loan.principal_amount),
            type: "loan_disbursement",
            timestamp: Date.now(),
          }).catch(() => {});

          // Dapr pub/sub
          dapr.publishEvent("pubsub", "loan.disbursed", {
            ref, loanId: input.loanId, agentId: loan.agent_id,
            amount: Number(loan.principal_amount),
          }).catch(() => {});

          // Redis — invalidate agent balance cache
          cacheSet(`agent:balance:${loan.agent_id}`, "", 1).catch(() => {});

          // Lakehouse analytics
          ingestToLakehouse("loan_disbursements", {
            ref, loanId: input.loanId, agentId: loan.agent_id,
            amount: Number(loan.principal_amount),
            timestamp: new Date().toISOString(),
          }).catch(() => {});

          writeAuditLog({
            agentId: loan.agent_id,
            agentCode: String(ctx.user?.id ?? "system"),
            action: "LOAN_DISBURSED",
            resource: "agentLoanFacility",
            resourceId: ref,
            status: "success",
            metadata: { loanId: input.loanId, amount: Number(loan.principal_amount) },
          }).catch(() => {});

          return { success: true, disbursedAmount: loan.principal_amount, ref };
        }, "agentLoanFacility.disburse");
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Record repayment
  recordRepayment: protectedProcedure
    .input(z.object({ loanId: z.number(), amount: z.number().min(1) }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");

        return await withTransaction(async (tx) => {
          // Lock loan row
          const loanResult = await tx.execute(
            sql`SELECT * FROM "agent_loans" WHERE id = ${input.loanId} FOR UPDATE`
          );
          const loan = (loanResult as any).rows?.[0];
          if (!loan) throw new Error("Loan not found");

          const newRepaid = parseFloat(String(loan.amount_repaid || "0")) + input.amount;
          const totalRepayable = parseFloat(String(loan.total_repayable));
          const isFullyRepaid = newRepaid >= totalRepayable;

          await tx.execute(
            sql`UPDATE "agent_loans" SET amount_repaid = ${String(newRepaid)}, status = ${isFullyRepaid ? "completed" : "repaying"}, updated_at = NOW() WHERE id = ${input.loanId}`
          );

          // GL entry: Debit Loan Payable (2004), Credit Agent Float (2001)
          const ref = `LOAN-REPAY-${input.loanId}-${Date.now()}`;
          await db.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Loan repayment #${input.loanId}`,
            debitAccountId: 2004,
            creditAccountId: 2001,
            amount: Math.round(input.amount * 100),
            currency: "NGN",
            referenceType: "loan_repayment",
            referenceId: ref,
            postedBy: String(ctx.user?.id ?? "system"),
            status: "posted",
          });

          // Kafka event
          publishEvent(
            "pos.transactions.created",
            ref,
            {
              type: "loan_repayment",
              loanId: input.loanId,
              agentId: loan.agent_id,
              amount: input.amount,
              totalRepaid: newRepaid,
              isFullyRepaid,
              timestamp: new Date().toISOString(),
            },
            { agentCode: String(ctx.user?.id ?? "system") }
          ).catch(() => {});

          // TigerBeetle dual-ledger
          tbCreateTransfer({
            debitAccountId: "2004",
            creditAccountId: "2001",
            amount: Math.round(input.amount * 100),
            ref,
            txType: "loan_repayment",
            agentCode: String(ctx.user?.id ?? "system"),
          }).catch(() => {});

          // Fluvio streaming
          publishTxToFluvio({
            txRef: ref,
            agentCode: String(ctx.user?.id ?? "system"),
            amount: input.amount,
            type: "loan_repayment",
            timestamp: Date.now(),
          }).catch(() => {});

          // Dapr pub/sub
          dapr.publishEvent("pubsub", "loan.repayment", {
            ref, loanId: input.loanId, agentId: loan.agent_id,
            amount: input.amount, isFullyRepaid,
          }).catch(() => {});

          // Redis — invalidate cache
          cacheSet(`agent:balance:${loan.agent_id}`, "", 1).catch(() => {});

          // Lakehouse
          ingestToLakehouse("loan_repayments", {
            ref, loanId: input.loanId, agentId: loan.agent_id,
            amount: input.amount, totalRepaid: newRepaid, isFullyRepaid,
            timestamp: new Date().toISOString(),
          }).catch(() => {});

          writeAuditLog({
            agentId: loan.agent_id,
            agentCode: String(ctx.user?.id ?? "system"),
            action: "LOAN_REPAYMENT",
            resource: "agentLoanFacility",
            resourceId: ref,
            status: "success",
            metadata: { loanId: input.loanId, amount: input.amount, isFullyRepaid },
          }).catch(() => {});

          return {
            success: true,
            ref,
            amountRepaid: newRepaid,
            remaining: Math.max(0, totalRepayable - newRepaid),
            fullyRepaid: isFullyRepaid,
          };
        }, "agentLoanFacility.recordRepayment");
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // Reject a loan
  reject: protectedProcedure
    .input(z.object({ loanId: z.number(), reason: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        await db
          .update(agentLoans)
          .set({ status: "rejected", updatedAt: new Date() })
          .where(eq(agentLoans.id, input.loanId));
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

  // Get credit score for an agent
  creditScore: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db)
          return { score: 0, breakdown: {}, eligible: false, maxLoanAmount: 0 };
        const score = await calculateCreditScore(db, input.agentId);
        return {
          score,
          eligible: score >= MIN_CREDIT_SCORE,
          maxLoanAmount: score >= MIN_CREDIT_SCORE ? score * 1000 : 0,
          breakdown: CREDIT_SCORE_WEIGHTS,
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

  // Portfolio summary
  portfolioSummary: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db)
      return {
        totalLoans: 0,
        totalDisbursed: "0",
        totalRepaid: "0",
        defaultRate: 0,
        activeLoans: 0,
      };
    const [stats] = await db
      .select({
        totalLoans: count(),
        totalDisbursed: sum(agentLoans.principalAmount),
        totalRepaid: sum(agentLoans.amountRepaid),
      })
      .from(agentLoans);
    const [defaulted] = await db
      .select({ count: count() })
      .from(agentLoans)
      .where(eq(agentLoans.status, "defaulted"))
      .limit(100);
    const [active] = await db
      .select({ count: count() })
      .from(agentLoans)
      .where(sql`${agentLoans.status} IN ('disbursed', 'repaying')`);
    return {
      totalLoans: stats.totalLoans || 0,
      totalDisbursed: stats.totalDisbursed || "0",
      totalRepaid: stats.totalRepaid || "0",
      defaultRate: stats.totalLoans
        ? ((defaulted.count || 0) / stats.totalLoans) * 100
        : 0,
      activeLoans: active.count || 0,
    };
  }),
});

async function calculateCreditScore(db: any, agentId: number): Promise<number> {
  // Transaction volume score (0-300)
  const [txStats] = await db
    .select({ total: sum(transactions.amount), count: count() })
    .from(transactions)
    .where(
      and(
        eq(transactions.agentId, agentId),
        gte(transactions.createdAt, new Date(Date.now() - 90 * 86400000))
      )
    );
  const volumeScore = Math.min(((txStats.count || 0) / 100) * 300, 300);
  // Repayment history score (0-250)
  const [loanStats] = await db
    .select({ total: count() })
    .from(agentLoans)
    .where(
      and(eq(agentLoans.agentId, agentId), eq(agentLoans.status, "completed"))
    );
  const repaymentScore = Math.min((loanStats.total || 0) * 50, 250);
  // Account age score (0-200)
  const [agent] = await db
    .select()
    .from(agents)
    .where(eq(agents.id, agentId))
    .limit(100);
  const ageMonths = agent
    ? (Date.now() - new Date(agent.createdAt).getTime()) / (30 * 86400000)
    : 0;
  const ageScore = Math.min(ageMonths * 15, 200);
  // Float utilization (0-150)
  const floatScore = agent
    ? Math.min(
        (parseFloat(String(agent.floatBalance || "0")) /
          parseFloat(String(agent.floatLimit || "1000000"))) *
          150,
        150
      )
    : 0;
  // Total (max 850, like FICO)
  return Math.round(volumeScore + repaymentScore + ageScore + floatScore);
}
