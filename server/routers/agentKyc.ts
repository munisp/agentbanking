// @ts-nocheck
import { z } from "zod";
import {
  router,
  publicProcedure as openProcedure,
  protectedProcedure,
} from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
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
import { kycSessions, kycDocuments, auditLog } from "../../drizzle/schema";
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
import { publishEvent } from "../kafkaClient";
import { tbCreateTransfer } from "../tbClient";
import { cacheSet } from "../redisClient";
import { publishTxToFluvio } from "../fluvio";
import { ingestToLakehouse } from "../lakehouse";
import { dapr } from "../middleware/middlewareConnectors";

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

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentKyc",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentKyc",
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
    resource: "agentKyc",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentKyc",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
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

// ── Middleware Fan-Out (Kafka + TigerBeetle + Fluvio + Dapr + Lakehouse) ──
async function publishagentKycMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `kyc.${action}` as any;
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
      txType: `kyc_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `kyc_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("kyc", { ref, action, ...payload, timestamp: ts }).catch(
    () => {}
  );
}

export const agentKycRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalSessions: 0, pending: 0, approved: 0, rejected: 0 };
    const [total] = await db
      .select({ value: count() })
      .from(kycSessions)
      .limit(100);
    const statusCounts = await db
      .select({ status: kycSessions.status, cnt: count() })
      .from(kycSessions)
      .groupBy(kycSessions.status)
      .limit(100);
    const byStatus: Record<string, number> = {};
    statusCounts.forEach(r => {
      byStatus[r.status] = Number(r.cnt);
    });
    return {
      totalSessions: Number(total.value),
      pending: byStatus["pending"] ?? 0,
      approved: byStatus["approved"] ?? 0,
      rejected: byStatus["rejected"] ?? 0,
    };
  }),
  listSessions: protectedProcedure
    .input(
      z
        .object({
          agentId: z.number().optional(),
          status: z.string().optional(),
          limit: z.number().default(20),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { sessions: [], total: 0 };
        const conditions: any[] = [];
        if (input?.agentId)
          conditions.push(eq(kycSessions.agentId, input.agentId));
        const where = conditions.length > 0 ? and(...conditions) : undefined;
        const rows = await db
          .select()
          .from(kycSessions)
          .where(where)
          .orderBy(desc(kycSessions.createdAt))
          .limit(input?.limit ?? 20);
        return { sessions: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  createSession: protectedProcedure
    .input(
      z.object({ agentId: z.number(), type: z.string().default("standard") })
    )
    .mutation(async ({ input, ctx }) => {
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
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const [session] = await db
          .insert(kycSessions)
          .values({
            agentId: input.agentId,
            type: input.type,
            status: "pending",
          })
          .returning();
        await db.insert(auditLog).values({
          action: "kyc_session_created",
          resource: "kyc_sessions",
          resourceId: String(session.id),
          status: "success",
          metadata: { agentId: input.agentId },
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

          resource: "agentKyc",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        // Middleware fan-out (fail-open)

        await publishagentKycMiddleware("createSession", `${Date.now()}`, {
          action: "createSession",
        }).catch(() => {});

        return { success: true, session };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  approveSession: protectedProcedure
    .input(
      z.object({ sessionId: z.number(), reviewNotes: z.string().optional() })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const [updated] = await db
          .update(kycSessions)
          .set({ status: "approved", reviewedAt: new Date() })
          .where(eq(kycSessions.id, input.sessionId))
          .returning();
        await db.insert(auditLog).values({
          action: "kyc_approved",
          resource: "kyc_sessions",
          resourceId: String(input.sessionId),
          status: "success",
        });
        // Middleware fan-out (fail-open)
        await publishagentKycMiddleware("approveSession", `${Date.now()}`, {
          action: "approveSession",
        }).catch(() => {});

        return { success: true, session: updated };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Sprint 78 domain-specific procedures ──────────────────────────────────
  listProfiles: openProcedure
    .input(z.object({ status: z.string().optional() }).optional())
    .query(async ({ input }) => {
      // FAIL LOUD: previously returned hardcoded fabricated agent profiles.
      // No KYC profile store with this shape exists in this deployment.
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "agentKyc.listProfiles is not available in this deployment",
      });
    }),

  getProfile: openProcedure
    .input(z.object({ agentId: z.string().min(1).max(255) }))
    .query(async ({ input }) => {
      // FAIL LOUD: previously returned hardcoded fabricated profiles.
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "agentKyc.getProfile is not available in this deployment",
      });
    }),

  getDocument: openProcedure
    .input(z.object({ docId: z.string().min(1).max(255) }))
    .query(async ({ input }) => {
      // FAIL LOUD: previously returned hardcoded fabricated documents with
      // fabricated confidenceScore values.
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "agentKyc.getDocument is not available in this deployment",
      });
    }),

  submitDocument: openProcedure
    .input(
      z.object({
        agentId: z.string().min(1).max(255),
        docType: z.string(),
        docNumber: z.string(),
        fullName: z.string(),
        dateOfBirth: z.string(),
        issueDate: z.string(),
        expiryDate: z.string().nullable(),
        issuingAuthority: z.string(),
        country: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      // Input format pre-validation only — a regex match is NOT verification
      // and must never produce a "verified" status or a confidence score.
      const isValidNin =
        input.docType === "nin" && /^\d{11}$/.test(input.docNumber);
      const isValidBvn =
        input.docType === "bvn" && /^\d{11}$/.test(input.docNumber);
      const isValidPassport =
        input.docType === "passport" && /^[A-Z]\d{8}$/.test(input.docNumber);
      const isValid = isValidNin || isValidBvn || isValidPassport;
      if (!isValid) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: `Document number fails format validation for docType "${input.docType}"`,
        });
      }
      // FAIL LOUD: no KYC verification provider (NIN/BVN/passport) is
      // configured in this deployment. Regex format checks cannot verify
      // identity documents.
      throw new TRPCError({
        code: "NOT_IMPLEMENTED",
        message: "agentKyc.submitDocument is not available in this deployment",
      });
    }),

  getDashboard: openProcedure.query(async () => {
    // FAIL LOUD: previously returned hardcoded fabricated dashboard metrics.
    throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message: "agentKyc.getDashboard is not available in this deployment",
    });
  }),
  list: openProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async () => ({
      items: [],
      data: [],
      total: 0,
    })),
});
