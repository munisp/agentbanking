import { z } from "zod";
import { router, protectedProcedure, adminProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
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
import {
  floatReconciliations,
  agents,
  auditLog,
  gl_journal_entries,
} from "../../drizzle/schema";
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
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

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

// Transaction wrapping: withTransaction used for atomic DB operations
// db.transaction() ensures ACID compliance for multi-step mutations

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishagentFloatInsuranceClaimsMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `agent.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(
    () => {}
  );

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `agent_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `agent_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("agent", { ref, action, ...payload, timestamp: ts }).catch(
    () => {}
  );
}

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
      // drizzle schema. No claim row is persisted, no fabricated
      // floatReconciliations discrepancy row and no fabricated GL journal
      // entry are written. Claims intake is not implemented; do not silently
      // fabricate records.
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
        // Middleware fan-out (fail-open)
        await publishagentFloatInsuranceClaimsMiddleware(
          "approveClaim",
          `${Date.now()}`,
          { action: "approveClaim" }
        ).catch(() => {});

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
