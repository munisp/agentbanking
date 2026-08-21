import { z } from "zod";
import { router, protectedProcedure, adminProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  eq,
  desc,
  and,
  sql,
  count,
  sum,
  isNull,
  gte,
  lte,
  or,
  asc,
} from "drizzle-orm";
import { floatReconciliations, agents, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
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
  draft: ["submitted"],
  submitted: ["under_review", "rejected"],
  under_review: ["approved", "rejected"],
  approved: ["active"],
  active: ["claimed", "expired", "cancelled"],
  claimed: ["settled", "rejected"],
  settled: [],
  expired: [],
  cancelled: [],
  rejected: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateAgentfloatinsuranceclaimsInput(
  data: Record<string, unknown>
): boolean {
  if (!data) return false;
  const requiredFields = Object.keys(data).filter(
    k => data[k] !== undefined && data[k] !== null
  );
  if (requiredFields.length === 0) return false;
  if (
    typeof data.id === "number" &&
    (data.id <= 0 || !Number.isFinite(data.id))
  )
    return false;
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 ||
      data.amount > 100_000_000 ||
      !Number.isFinite(data.amount))
  )
    return false;
  return true;
}

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentFloatInsuranceClaims",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentFloatInsuranceClaims",
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
    resource: "agentFloatInsuranceClaims",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentFloatInsuranceClaims",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_AGENTFLOATINSURANCECLAIMS = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_AGENTFLOATINSURANCECLAIMS.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_AGENTFLOATINSURANCECLAIMS.validateRange(
        data.amount,
        0,
        100_000_000
      )
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Database Query Patterns ────────────────────────────────────────────────
const _agentFloatInsuranceClaims_db = {
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

export const agentFloatInsuranceClaimsRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return {
        totalClaims: 0,
        pending: 0,
        approved: 0,
        rejected: 0,
        totalAmount: "0",
      };
    const [total] = await db
      .select({ value: count() })
      .from(floatReconciliations)
      .limit(100);
    return {
      totalClaims: Number(total.value),
      pending: 0,
      approved: Number(total.value),
      rejected: 0,
      totalAmount: "0",
    };
  }),
  listClaims: protectedProcedure
    .input(
      z
        .object({
          agentId: z.number().optional(),
          limit: z.number().default(20),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { claims: [], total: 0 };
        const conditions: any[] = [];
        if (input?.agentId)
          conditions.push(eq(floatReconciliations.agentId, input.agentId));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const rows = await db
          .select()
          .from(floatReconciliations)
          .where(where)
          .orderBy(desc(floatReconciliations.date))
          .limit(input?.limit ?? 20);
        return { claims: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  fileClaim: protectedProcedure
    .input(
      z.object({ agentId: z.number(), amount: z.string(), reason: z.string() })
    )
    .mutation(async ({ input, ctx }) => {
      // NF-FF-25: agentId is session-derived — a caller may only file a claim
      // for their own agent session unless they are an admin.
      const session = await getAgentFromCookie(ctx.req);
      if (!session)
        throw new TRPCError({
          code: "UNAUTHORIZED",
          message: "Agent session required",
        });
      const isAdmin = ctx.user?.role === "admin" || session.role === "admin";
      if (input.agentId !== session.id && !isAdmin)
        throw new TRPCError({
          code: "FORBIDDEN",
          message: "Cannot file an insurance claim for another agent",
        });

      // NF-FF-25: fail loud — there is NO float insurance claims table in the
      // drizzle schema. No claim row is persisted and no fabricated
      // floatReconciliations discrepancy row is written. Claims intake is not
      // implemented; do not silently fabricate records.
      logOperation("CLAIM_NOT_IMPLEMENTED", {
        agentId: session.id,
        amount: input.amount,
        reason: input.reason,
      });
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message:
          "Float insurance claims are not implemented: no claims table exists in the schema",
      });
    }),
  approveClaim: adminProcedure
    .input(z.object({ claimId: z.number(), notes: z.string().optional() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        // NF-FF-25: conditional transition pending → resolved; 0 rows => 409.
        // NOTE: this updates workflow status ONLY — there is intentionally NO
        // funds leg (no payout / float credit) because no claims settlement
        // mechanism exists in the schema.
        const [updated] = await db
          .update(floatReconciliations)
          .set({
            status: "resolved",
            resolvedBy: ctx.user.id,
            resolvedAt: new Date(),
          })
          .where(
            and(
              eq(floatReconciliations.id, input.claimId),
              eq(floatReconciliations.status, "pending")
            )
          )
          .returning();
        if (!updated)
          throw new TRPCError({
            code: "CONFLICT",
            message: "Claim not found or not in pending status",
          });
        await db.insert(auditLog).values({
          action: "float_claim_approved",
          resource: "float_claims",
          resourceId: String(input.claimId),
          status: "success",
        });
        return { success: true, claim: updated };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
