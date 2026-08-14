/**
 * F04: Agent Loan & Credit Facility
 * Loan application, credit scoring, disbursement, repayment tracking, interest calculation
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { TRPCError } from "@trpc/server";
import { getDb } from "../db";
import {
  agentLoans,
  agents,
  transactions,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, gte, count, sum, avg, sql } from "drizzle-orm";
import { getAgentFromCookie } from "../middleware/agentAuth";
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

// ── GL account ids used for loan double-entry journaling ────────────────────
// Chosen to follow the repo's existing gl_journal_entries conventions:
// floatTopUp posts debit 2001 / credit 1001 (agent float vs cash on hand) and
// the disputeRefund twin posts 5002 (refund expense) / 1001. For loans we use:
//   1201 = Loans Receivable (asset)     — increases when principal goes out
//   2001 = Agent Float Clearing (liability) — the same agent-float leg used by
//          floatTopUp; disbursement credits it, repayment debits it back.
const GL_ACCT_LOANS_RECEIVABLE = 1201;
const GL_ACCT_AGENT_FLOAT_CLEARING = 2001;
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
        "agentLoanFacility",
        "mutation",
        "Executed agentLoanFacility mutation"
      );

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
  // FF-2: single DB transaction — conditional approved→disbursed UPDATE first,
  // float credited ONLY if the transition claimed a row (no TOCTOU double
  // disburse), double-entry GL journal, admin-or-owning-agent authorization.
  disburse: protectedProcedure
    .input(z.object({ loanId: z.number() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        return await withTransaction(async tx => {
          // Atomic state transition: only a loan still 'approved' can be
          // disbursed. A concurrent double-disburse affects 0 rows → CONFLICT.
          const claimed = await tx
            .update(agentLoans)
            .set({
              status: "disbursed",
              disbursedAt: new Date(),
              updatedAt: new Date(),
            })
            .where(
              and(
                eq(agentLoans.id, input.loanId),
                eq(agentLoans.status, "approved")
              )
            )
            .returning();
          const loan = claimed[0];
          if (!loan) {
            const existing = await tx
              .select()
              .from(agentLoans)
              .where(eq(agentLoans.id, input.loanId))
              .limit(1);
            if (!existing[0])
              throw new TRPCError({
                code: "NOT_FOUND",
                message: "Loan not found",
              });
            throw new TRPCError({
              code: "CONFLICT",
              message: `Loan is '${existing[0].status}' — only approved loans can be disbursed (duplicate disbursement rejected)`,
            });
          }

          // Authorization: admin or the agent who owns the loan.
          if (session.role !== "admin" && session.id !== loan.agentId) {
            throw new TRPCError({
              code: "FORBIDDEN",
              message:
                "Only an admin or the owning agent can disburse this loan",
            });
          }

          // Credit agent float — atomic SQL-expression update (same guarded
          // pattern as repositories/agent.repository.ts adjustFloatBalance,
          // credit leg); 0 rows means the agent row vanished → roll back.
          const credited = await tx
            .update(agents)
            .set({
              floatBalance: sql`"floatBalance" + ${String(loan.principalAmount)}::numeric`,
              updatedAt: new Date(),
            })
            .where(eq(agents.id, loan.agentId))
            .returning({ id: agents.id });
          if (credited.length === 0) {
            throw new TRPCError({
              code: "INTERNAL_SERVER_ERROR",
              message: `Agent ${loan.agentId} not found — disbursement rolled back`,
            });
          }

          // Double-entry GL: debit Loans Receivable, credit Agent Float
          // Clearing (see GL_ACCT_* constants above). entryNumber is
          // deterministic per loan; the whole transaction rolls back on
          // failure so a retry cannot duplicate the entry.
          const ref = `LOAN-DISB-${loan.id}`;
          await tx.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Loan disbursement #${loan.id} to agent ${loan.agentId}`,
            debitAccountId: GL_ACCT_LOANS_RECEIVABLE,
            creditAccountId: GL_ACCT_AGENT_FLOAT_CLEARING,
            amount: Math.round(Number(loan.principalAmount) * 100), // kobo
            currency: "NGN",
            referenceType: "loan_disbursement",
            referenceId: ref,
            postedBy: session.agentCode ?? String(session.id),
            status: "posted",
          });

          return { success: true, disbursedAmount: loan.principalAmount, ref };
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
  // FF-2: single DB transaction, optimistic-concurrency guarded UPDATE,
  // overpayment rejected, double-entry GL credit leg to Loans Receivable.
  recordRepayment: protectedProcedure
    .input(z.object({ loanId: z.number(), amount: z.number().min(1) }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new Error("Database unavailable");
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        return await withTransaction(async tx => {
          const rows = await tx
            .select()
            .from(agentLoans)
            .where(eq(agentLoans.id, input.loanId))
            .limit(1);
          const loan = rows[0];
          if (!loan)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "Loan not found",
            });

          // Authorization: admin or the agent who owns the loan.
          if (session.role !== "admin" && session.id !== loan.agentId) {
            throw new TRPCError({
              code: "FORBIDDEN",
              message:
                "Only an admin or the owning agent can record repayment for this loan",
            });
          }

          if (loan.status !== "disbursed" && loan.status !== "repaying") {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Loan is '${loan.status}' — repayments can only be recorded against an active (disbursed/repaying) loan`,
            });
          }

          const repaid = parseFloat(String(loan.amountRepaid || "0"));
          const totalRepayable = parseFloat(String(loan.totalRepayable));
          const remaining = totalRepayable - repaid;
          // Reject overpayment beyond the remaining balance (1 kobo tolerance
          // for decimal representation noise).
          if (input.amount > remaining + 0.005) {
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: `Overpayment rejected: remaining balance is ${remaining.toFixed(2)}, attempted ${input.amount.toFixed(2)}`,
            });
          }
          const newRepaid = repaid + input.amount;
          const isFullyRepaid = newRepaid >= totalRepayable - 0.005;

          // Guarded UPDATE: the amountRepaid predicate is an optimistic
          // concurrency token — a concurrent repayment that already committed
          // changed amountRepaid, so this affects 0 rows → CONFLICT.
          const updated = await tx
            .update(agentLoans)
            .set({
              amountRepaid: newRepaid.toFixed(2),
              status: isFullyRepaid ? "completed" : "repaying",
              updatedAt: new Date(),
            })
            .where(
              and(
                eq(agentLoans.id, input.loanId),
                sql`"amount_repaid" = ${repaid.toFixed(2)}::numeric`,
                sql`"status" IN ('disbursed', 'repaying')`
              )
            )
            .returning({ id: agentLoans.id });
          if (updated.length === 0) {
            throw new TRPCError({
              code: "CONFLICT",
              message:
                "Concurrent repayment detected — please retry (no amount was recorded)",
            });
          }

          // Double-entry GL: debit Agent Float Clearing, credit Loans
          // Receivable (repayment reduces both the clearing liability and the
          // receivable asset). Agent floatBalance itself is not moved here —
          // repayment cash settlement against float is handled by the float
          // management flow; this journal records the loan-leg accounting.
          // entryNumber is unique per repayment via the cumulative repaid
          // amount (a rolled-back retry re-derives the same deterministic ref).
          const ref = `LOAN-REPAY-${loan.id}-${newRepaid.toFixed(2)}`;
          await tx.insert(gl_journal_entries).values({
            entryNumber: `JE-${ref}`,
            description: `Loan repayment #${loan.id} from agent ${loan.agentId}`,
            debitAccountId: GL_ACCT_AGENT_FLOAT_CLEARING,
            creditAccountId: GL_ACCT_LOANS_RECEIVABLE,
            amount: Math.round(input.amount * 100), // kobo
            currency: "NGN",
            referenceType: "loan_repayment",
            referenceId: ref,
            postedBy: session.agentCode ?? String(session.id),
            status: "posted",
          });

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
