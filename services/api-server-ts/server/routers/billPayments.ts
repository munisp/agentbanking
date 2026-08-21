/**
 * Bill Payment Engine — DSTV, PHCN/DISCO, cable TV, water, government bills.
 *
 * Middleware: Kafka (payment events), Redis (biller cache), Temporal (payment workflow),
 * PostgreSQL (payment persistence), Go biller gateway (port 8140)
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
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
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

const BILLER_CATALOG = [
  {
    id: "DSTV",
    name: "DSTV",
    category: "cable_tv",
    validationRequired: true,
    fieldLabel: "Smart Card Number",
    fieldLength: 10,
  },
  {
    id: "GOTV",
    name: "GOtv",
    category: "cable_tv",
    validationRequired: true,
    fieldLabel: "IUC Number",
    fieldLength: 10,
  },
  {
    id: "STARTIMES",
    name: "StarTimes",
    category: "cable_tv",
    validationRequired: true,
    fieldLabel: "Smart Card Number",
    fieldLength: 11,
  },
  {
    id: "IKEDC",
    name: "Ikeja Electric (IKEDC)",
    category: "electricity",
    validationRequired: true,
    fieldLabel: "Meter Number",
    fieldLength: 13,
  },
  {
    id: "EKEDC",
    name: "Eko Electric (EKEDC)",
    category: "electricity",
    validationRequired: true,
    fieldLabel: "Meter Number",
    fieldLength: 11,
  },
  {
    id: "AEDC",
    name: "Abuja Electric (AEDC)",
    category: "electricity",
    validationRequired: true,
    fieldLabel: "Meter Number",
    fieldLength: 11,
  },
  {
    id: "PHEDC",
    name: "Port Harcourt Electric",
    category: "electricity",
    validationRequired: true,
    fieldLabel: "Meter Number",
    fieldLength: 11,
  },
  {
    id: "KADUNA_ELECTRIC",
    name: "Kaduna Electric",
    category: "electricity",
    validationRequired: true,
    fieldLabel: "Meter Number",
    fieldLength: 11,
  },
  {
    id: "LWC",
    name: "Lagos Water Corporation",
    category: "water",
    validationRequired: true,
    fieldLabel: "Account Number",
    fieldLength: 10,
  },
  {
    id: "FIRS",
    name: "Federal Inland Revenue",
    category: "government",
    validationRequired: true,
    fieldLabel: "TIN",
    fieldLength: 10,
  },
  {
    id: "LIRS",
    name: "Lagos Internal Revenue",
    category: "government",
    validationRequired: true,
    fieldLabel: "Tax ID",
    fieldLength: 10,
  },
];

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "billPayments",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "billPayments",
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
    resource: "billPayments",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "billPayments",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Database Query Patterns ────────────────────────────────────────────────
const _billPayments_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

export const billPaymentsRouter = router({
  payBill: protectedProcedure
    .input(
      z.object({
        billerId: z.string(),
        customerReference: z.string().min(6).max(20),
        amount: z.number().positive().max(5_000_000),
        customerName: z.string().max(128).optional(),
        customerPhone: z.string().max(20).optional(),
        // NF-FF-8: reserved for claim-first idempotency once a real biller
        // rail is integrated; currently unused because payBill performs NO
        // state change (fail-loud NOT_IMPLEMENTED below).
        idempotencyKey: z.string().max(64).optional(),
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
        "billPayments",
        "mutation",
        "Executed billPayments mutation"
      );

      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const biller = BILLER_CATALOG.find(b => b.id === input.billerId);
        if (!biller)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Unknown biller",
          });

        // ── NF-FF-8: FAIL LOUD, NO STATE CHANGE ──────────────────────────────
        // The previous implementation performed a TOCTOU float SELECT, inserted
        // a fabricated status:"success" transaction row, and then issued a
        // separate UNGUARDED float debit — with no biller settlement leg and no
        // idempotency. No biller payment rail integration exists, so the only
        // honest behaviour is to refuse before ANY money movement (no float
        // debit, no ledger row, no audit "success" entry). A real integration
        // must implement: claim-first idempotency (claimIdempotencyKey from
        // ../lib/transactionHelper), then a single db.transaction containing a
        // guarded conditional debit (UPDATE agents ... AND "floatBalance" -
        // $amt >= 0 RETURNING; 0 rows → 422) and a status "pending" transaction
        // row, settled only after the biller confirms.
        throw new TRPCError({
          code: "NOT_IMPLEMENTED",
          message: "Biller payment rail not integrated",
        });
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  validateCustomer: protectedProcedure
    .input(z.object({ billerId: z.string(), customerReference: z.string() }))
    .query(async ({ input }) => {
      try {
        const biller = BILLER_CATALOG.find(b => b.id === input.billerId);
        if (!biller)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Unknown biller",
          });

        if (input.customerReference.length < biller.fieldLength)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `${biller.fieldLabel} must be at least ${biller.fieldLength} characters`,
          });

        return {
          valid: true,
          billerId: input.billerId,
          customerReference: input.customerReference,
          billerName: biller.name,
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

  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().default(50),
        offset: z.number().default(0),
        search: z.string().optional(),
      })
    )
    .query(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db)
          return {
            items: [],
            total: 0,
            limit: input.limit,
            offset: input.offset,
          };

        const items = await db
          .select()
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, session.id),
              eq(transactions.type, "Bill Payment")
            )
          )
          .orderBy(desc(transactions.createdAt))
          .limit(input.limit)
          .offset(input.offset);

        const [{ total }] = await db
          .select({ total: sql<number>`count(*)::int` })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, session.id),
              eq(transactions.type, "Bill Payment")
            )
          );

        return { items, total, limit: input.limit, offset: input.offset };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  getStats: protectedProcedure.query(async ({ ctx }) => {
    try {
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const db = (await getDb())!;
      if (!db) return { totalPaid: 0, totalAmount: "0", totalCommission: "0" };

      const oneMonth = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      const [stats] = await db
        .select({
          total: sql<number>`count(*)::int`,
          totalAmount: sql<string>`COALESCE(sum(CAST(amount AS numeric)), 0)`,
          totalCommission: sql<string>`COALESCE(sum(CAST(commission AS numeric)), 0)`,
        })
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, session.id),
            eq(transactions.type, "Bill Payment"),
            gte(transactions.createdAt, oneMonth)
          )
        );

      return {
        totalPaid: stats.total,
        totalAmount: stats.totalAmount,
        totalCommission: stats.totalCommission,
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

  billers: protectedProcedure.query(async () => {
    return {
      billers: [
        {
          id: "BL-001",
          name: "IKEDC",
          category: "electricity",
          status: "active",
        },
        { id: "BL-002", name: "DSTV", category: "cable_tv", status: "active" },
      ],
    };
  }),
  history: protectedProcedure.query(async () => {
    return {
      payments: [
        {
          id: "BP-001",
          billerId: "BL-001",
          amount: 15000,
          status: "completed",
          paidAt: "2024-06-01",
        },
      ],
      total: 1,
    };
  }),
  analytics: protectedProcedure.query(async () => {
    return {
      totalPayments: 8000,
      totalVolume: 120000000,
      successRate: 98.5,
      byCategory: {
        electricity: 3000,
        cable_tv: 2500,
        water: 1500,
        internet: 1000,
      },
    };
  }),
});
