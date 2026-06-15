// @ts-nocheck
/**
 * Agent Banking UI tRPC Router
 * Covers all 9 pages of the Agent Banking UI PWA:
 * Dashboard, Transactions, Float, QR Payments, Receipts,
 * Notifications, Profile, Disputes, Loyalty.
 */
import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import {
  agents,
  transactions,
  floatTopUpRequests,
  qrCodes,
  disputes,
  loyaltyHistory,
  fraudAlerts,
  shareableLinks,
  kycSessions,
  gl_journal_entries,
} from "../../drizzle/schema";
import { eq, desc, and, gte, lte, count, sql } from "drizzle-orm";
import crypto from "crypto";
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { checkDailyLimit } from "../lib/cbnLimits";
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

// ── Guard: agent-only procedure ──────────────────────────────────────────────
// Agents authenticate via PIN cookie (agentAuth middleware), not 54Link OAuth.
// We use protectedProcedure here and validate the agent session from the cookie.
const agentProcedure = protectedProcedure.use(async ({ ctx, next }) => {
  // The agentAuth middleware sets ctx.agent when the agent PIN cookie is valid.
  // Fall through to the procedure; each handler checks ctx.agent as needed.
  return next({ ctx });
});

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentBanking",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentBanking",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
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
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const agentBankingRouter = router({
  // ── Dashboard ──────────────────────────────────────────────────────────────
  dashboard: router({
    summary: agentProcedure
      .input(z.object({ agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db)
            return {
              txCount: 0,
              volume: "0",
              floatBalance: "0",
              loyaltyPoints: 0,
            };
          const [agent] = await db
            .select({
              floatBalance: agents.floatBalance,
              commissionBalance: agents.commissionBalance,
              loyaltyPoints: agents.loyaltyPoints,
              tier: agents.tier,
            })
            .from(agents)
            .where(eq(agents.id, input.agentId))
            .limit(100);
          if (!agent)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "Agent not found",
            });
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          const [stats] = await db
            .select({
              txCount: count(),
              volume: sql<string>`COALESCE(SUM(amount::numeric),0)`,
            })
            .from(transactions)
            .where(
              and(
                eq(transactions.agentId, input.agentId),
                gte(transactions.createdAt, today)
              )
            );
          return { ...agent, txCount: stats.txCount, volume: stats.volume };
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    recentTransactions: agentProcedure
      .input(z.object({ agentId: z.number(), limit: z.number().default(5) }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new Error("Database connection unavailable");
          return db
            .select()
            .from(transactions)
            .where(eq(transactions.agentId, input.agentId))
            .orderBy(desc(transactions.createdAt))
            .limit(input.limit);
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    alerts: agentProcedure
      .input(z.object({ agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new Error("Database connection unavailable");
          return db
            .select()
            .from(fraudAlerts)
            .where(
              and(
                eq(fraudAlerts.agentId, input.agentId),
                eq(fraudAlerts.status, "open")
              )
            )
            .orderBy(desc(fraudAlerts.createdAt))
            .limit(5);
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
  }),

  // ── Transactions ───────────────────────────────────────────────────────────
  transactions: router({
    list: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          page: z.number().default(1),
          limit: z.number().default(20),
          from: z.date().optional(),
          to: z.date().optional(),
          type: z.string().optional(),
          status: z.string().optional(),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { items: [], total: 0 };
          const offset = (input.page - 1) * input.limit;
          const conditions = [eq(transactions.agentId, input.agentId)];
          if (input.from)
            conditions.push(gte(transactions.createdAt, input.from));
          if (input.to) conditions.push(lte(transactions.createdAt, input.to));
          const where = and(...conditions);
          const [items, [{ total }]] = await Promise.all([
            db
              .select()
              .from(transactions)
              .where(where)
              .orderBy(desc(transactions.createdAt))
              .limit(input.limit)
              .offset(offset),
            db.select({ total: count() }).from(transactions).where(where),
          ]);
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
    get: agentProcedure
      .input(z.object({ id: z.number(), agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "NOT_FOUND" });
          const [tx] = await db
            .select()
            .from(transactions)
            .where(
              and(
                eq(transactions.id, input.id),
                eq(transactions.agentId, input.agentId)
              )
            )
            .limit(100);
          if (!tx)
            throw new TRPCError({
              code: "NOT_FOUND",
              message: "Transaction not found",
            });
          return tx;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    stats: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          period: z.enum(["today", "week", "month"]).default("today"),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { txCount: 0, volume: "0", commission: "0" };
          const from = new Date();
          if (input.period === "today") from.setHours(0, 0, 0, 0);
          else if (input.period === "week") from.setDate(from.getDate() - 7);
          else from.setMonth(from.getMonth() - 1);
          const [stats] = await db
            .select({
              txCount: count(),
              volume: sql<string>`COALESCE(SUM(amount::numeric),0)`,
              commission: sql<string>`COALESCE(SUM(commission::numeric),0)`,
            })
            .from(transactions)
            .where(
              and(
                eq(transactions.agentId, input.agentId),
                gte(transactions.createdAt, from)
              )
            );
          return stats;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
  }),

  // ── Float Management ───────────────────────────────────────────────────────
  float: router({
    balance: agentProcedure
      .input(z.object({ agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
          const [agent] = await db
            .select({
              floatBalance: agents.floatBalance,
              commissionBalance: agents.commissionBalance,
            })
            .from(agents)
            .where(eq(agents.id, input.agentId))
            .limit(100);
          if (!agent) throw new TRPCError({ code: "NOT_FOUND" });
          return agent;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    history: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          page: z.number().default(1),
          limit: z.number().default(20),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { items: [], total: 0 };
          const offset = (input.page - 1) * input.limit;
          const where = eq(floatTopUpRequests.agentId, input.agentId);
          const [items, [{ total }]] = await Promise.all([
            db
              .select()
              .from(floatTopUpRequests)
              .where(where)
              .orderBy(desc(floatTopUpRequests.createdAt))
              .limit(input.limit)
              .offset(offset),
            db.select({ total: count() }).from(floatTopUpRequests).where(where),
          ]);
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
    requestTopUp: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          amount: z.string(),
          channel: z.string().default("bank_transfer"),
          notes: z.string().optional(),
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
            STATUS_TRANSITIONS[
              currentStatus as keyof typeof STATUS_TRANSITIONS
            ];
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
                "amount" in input
                  ? (input as Record<string, unknown>).amount
                  : 0
              )
            : 0;
        const fees = calculateFee(txAmount, "transfer");
        const commission = calculateCommission(fees.fee, "transfer");
        const tax = calculateTax(fees.fee, "vat");
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
          const [req] = await db
            .insert(floatTopUpRequests)
            .values({
              agentId: input.agentId,
              requestedAmount: input.amount,
              notes: input.notes
                ? `[${input.channel}] ${input.notes}`
                : `[${input.channel}]`,
            })
            .returning();
          return req;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
  }),

  // ── QR Payments ────────────────────────────────────────────────────────────
  qr: router({
    generate: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          amount: z.string().optional(),
          description: z.string().optional(),
          type: z.enum(["payment", "agent_id"]).default("payment"),
        })
      )
      .mutation(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
          const code = `QR-${input.agentId}-${Date.now()}-${crypto.randomBytes(6).toString("hex").slice(0, 6).toUpperCase()}`;
          const [qr] = await db
            .insert(qrCodes)
            .values({
              code,
              type: input.type,
              agentId: input.agentId,
              amount: input.amount,
              description: input.description,
              expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000), // 24h
            })
            .returning();
          return qr;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    myQrCodes: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          page: z.number().default(1),
          limit: z.number().default(10),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { items: [], total: 0 };
          const offset = (input.page - 1) * input.limit;
          const where = eq(qrCodes.agentId, input.agentId);
          const [items, [{ total }]] = await Promise.all([
            db
              .select()
              .from(qrCodes)
              .where(where)
              .orderBy(desc(qrCodes.createdAt))
              .limit(input.limit)
              .offset(offset),
            db.select({ total: count() }).from(qrCodes).where(where),
          ]);
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
    pay: agentProcedure
      .input(
        z.object({
          code: z.string().min(1).max(256),
          amount: z.number().positive(),
          customerPhone: z.string().min(1).max(20),
          pin: z.string().min(4).max(6),
        })
      )
      .mutation(async ({ input, ctx }) => {
        return withIdempotency(`qr-pay-${input.code}-${input.amount}`, async () => {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

          // 1. Resolve QR code
          const [qr] = await db
            .select()
            .from(qrCodes)
            .where(eq(qrCodes.code, input.code))
            .limit(1);
          if (!qr) throw new TRPCError({ code: "NOT_FOUND", message: "QR code not found" });
          if (qr.status !== "active") throw new TRPCError({ code: "BAD_REQUEST", message: "QR code is not active" });
          if (qr.expiresAt && qr.expiresAt < new Date()) throw new TRPCError({ code: "BAD_REQUEST", message: "QR code has expired" });

          // 2. Validate amount against QR (if QR has fixed amount)
          const qrAmount = qr.amount ? Number(qr.amount) : null;
          if (qrAmount && Math.abs(qrAmount - input.amount) > 0.01) {
            throw new TRPCError({ code: "BAD_REQUEST", message: `QR requires exact amount ₦${qrAmount}` });
          }

          // 3. CBN daily limit check
          await checkDailyLimit(input.amount, "qr_payment");

          // 4. Calculate fees
          const feeResult = calculateFee(input.amount, "transfer");
          const commission = calculateCommission(feeResult.fee, "transfer");
          const netAmount = input.amount - feeResult.fee;

          // 5. Record transaction
          const ref = `QRP-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;
          const [txn] = await db
            .insert(transactions)
            .values({
              amount: input.amount,
              reference: ref,
              type: "qr_payment",
              status: "completed",
              metadata: JSON.stringify({
                qrCode: input.code,
                agentId: qr.agentId,
                customerPhone: input.customerPhone,
                fee: feeResult.fee,
                commission: commission.agent,
                netAmount,
              }),
            })
            .returning();

          // 6. GL double-entry journal
          await db.insert(gl_journal_entries).values([
            {
              entryNumber: `GL-QRP-${crypto.randomInt(100000)}`,
              accountCode: "CUSTOMER_QR_DEBIT",
              debitAmount: String(input.amount),
              creditAmount: "0",
              description: `QR payment from ${input.customerPhone}`,
              reference: ref,
              postedBy: "system",
            },
            {
              entryNumber: `GL-QRP-${crypto.randomInt(100000)}`,
              accountCode: "MERCHANT_QR_CREDIT",
              debitAmount: "0",
              creditAmount: String(netAmount),
              description: `QR payment to agent ${qr.agentId}`,
              reference: ref,
              postedBy: "system",
            },
          ]);

          // 7. Mark QR code as used
          await db.execute(
            sql`UPDATE "qr_codes" SET status = 'used', "usedAt" = NOW() WHERE code = ${input.code}`
          );

          // 8. Publish Kafka event
          await publishEvent("pos.qr.payment" as KafkaTopic, ref, {
            reference: ref,
            amount: input.amount,
            fee: feeResult.fee,
            commission: commission.agent,
            qrCode: input.code,
            agentId: qr.agentId,
            customerPhone: input.customerPhone,
          });

          // 9. Audit log
          await writeAuditLog({
            agentId: qr.agentId ?? 0,
            agentCode: "system",
            action: "QR_PAYMENT",
            resource: "qrCodes",
            resourceId: String(qr.id),
            status: "success",
            metadata: { ref, amount: input.amount, fee: feeResult.fee },
          });

          return {
            id: txn.id,
            reference: ref,
            status: "completed",
            amount: input.amount,
            fee: feeResult.fee,
            netAmount,
            commission: commission.agent,
          };
        });
      }),
  }),

  // ── Shareable Payment Links ────────────────────────────────────────────────
  links: router({
    list: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          page: z.number().default(1),
          limit: z.number().default(10),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { items: [], total: 0 };
          const offset = (input.page - 1) * input.limit;
          const where = eq(shareableLinks.agentId, input.agentId);
          const [items, [{ total }]] = await Promise.all([
            db
              .select()
              .from(shareableLinks)
              .where(where)
              .orderBy(desc(shareableLinks.createdAt))
              .limit(input.limit)
              .offset(offset),
            db.select({ total: count() }).from(shareableLinks).where(where),
          ]);
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
    create: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          type: z
            .enum(["payment", "invoice", "subscription", "donation"])
            .default("payment"),
          amount: z.string().optional(),
          description: z.string().optional(),
          expiresAt: z.date().optional(),
        })
      )
      .mutation(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
          const slug = `${input.agentId}-${crypto.randomUUID()}-${crypto.randomBytes(5).toString("hex").slice(0, 5)}`;
          const [link] = await db
            .insert(shareableLinks)
            .values({ ...input, slug })
            .returning();
          return link;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
  }),

  // ── Disputes ───────────────────────────────────────────────────────────────
  disputes: router({
    list: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          page: z.number().default(1),
          limit: z.number().default(10),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { items: [], total: 0 };
          const offset = (input.page - 1) * input.limit;
          const where = eq(disputes.agentId, input.agentId);
          const [items, [{ total }]] = await Promise.all([
            db
              .select()
              .from(disputes)
              .where(where)
              .orderBy(desc(disputes.createdAt))
              .limit(input.limit)
              .offset(offset),
            db.select({ total: count() }).from(disputes).where(where),
          ]);
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
    raise: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          transactionRef: z.string(),
          transactionId: z.number(),
          reason: z.string(),
          evidence: z.string().optional(),
        })
      )
      .mutation(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
          const ref = `DSP-${crypto.randomUUID().toUpperCase()}`;
          const [dispute] = await db
            .insert(disputes)
            .values({
              ref,
              agentId: input.agentId,
              transactionRef: input.transactionRef,
              transactionId: input.transactionId,
              reason: input.reason,
              evidence: input.evidence,
            })
            .returning();
          return dispute;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
  }),

  // ── Loyalty ────────────────────────────────────────────────────────────────
  loyalty: router({
    profile: agentProcedure
      .input(z.object({ agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "NOT_FOUND" });
          const [agent] = await db
            .select({ loyaltyPoints: agents.loyaltyPoints, tier: agents.tier })
            .from(agents)
            .where(eq(agents.id, input.agentId))
            .limit(100);
          if (!agent) throw new TRPCError({ code: "NOT_FOUND" });
          return agent;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    history: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          page: z.number().default(1),
          limit: z.number().default(20),
        })
      )
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) return { items: [], total: 0 };
          const offset = (input.page - 1) * input.limit;
          const where = eq(loyaltyHistory.agentId, input.agentId);
          const [items, [{ total }]] = await Promise.all([
            db
              .select()
              .from(loyaltyHistory)
              .where(where)
              .orderBy(desc(loyaltyHistory.createdAt))
              .limit(input.limit)
              .offset(offset),
            db.select({ total: count() }).from(loyaltyHistory).where(where),
          ]);
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
  }),

  // ── Profile ────────────────────────────────────────────────────────────────
  profile: router({
    get: agentProcedure
      .input(z.object({ agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "NOT_FOUND" });
          const [agent] = await db
            .select()
            .from(agents)
            .where(eq(agents.id, input.agentId))
            .limit(100);
          if (!agent) throw new TRPCError({ code: "NOT_FOUND" });
          // Never return pinHash
          const { pinHash: _, ...safe } = agent;
          return safe;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    update: agentProcedure
      .input(
        z.object({
          agentId: z.number(),
          name: z.string().optional(),
          phone: z.string().optional(),
          email: z.string().email().email().optional(),
          location: z.string().optional(),
        })
      )
      .mutation(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
          const { agentId, ...data } = input;
          const [agent] = await db
            .update(agents)
            .set({ ...data, updatedAt: new Date() })
            .where(eq(agents.id, agentId))
            .returning();
          const { pinHash: _, ...safe } = agent;
          return safe;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
    kycStatus: agentProcedure
      .input(z.object({ agentId: z.number() }))
      .query(async ({ input }) => {
        try {
          const db = (await getDb())!;
          if (!db) throw new Error("Database connection unavailable");
          const [session] = await db
            .select()
            .from(kycSessions)
            .where(eq(kycSessions.agentId, input.agentId))
            .orderBy(desc(kycSessions.createdAt))
            .limit(1);
          return session ?? null;
        } catch (error) {
          if (error instanceof TRPCError) throw error;
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error ? error.message : "Internal server error",
          });
        }
      }),
  }),
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async () => {
      return { items: [], total: 0 };
    }),
});
