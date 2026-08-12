import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { auditLog, notification_channels } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
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
  pending_verification: ["email_verified"],
  email_verified: ["profile_complete"],
  profile_complete: ["active"],
  active: ["suspended", "locked", "deactivated"],
  suspended: ["active", "deactivated"],
  locked: ["active", "deactivated"],
  deactivated: ["reactivation_pending"],
  reactivation_pending: ["active", "permanently_closed"],
  permanently_closed: [],
};

// Notification categories (16 across 4 groups):
// Transactions: txn_success, txn_failed, txn_pending, txn_reversed
// Security: sec_fraud, sec_login, sec_password, sec_mfa
// Financial: fin_settlement, fin_commission, fin_float, fin_payout
// System: sys_maintenance, sys_update, sys_alert, sys_report

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "userNotifPreferences",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "userNotifPreferences",
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
    resource: "userNotifPreferences",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "userNotifPreferences",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Error Handling ─────────────────────────────────────────────────────────
function handleError(error: unknown, context: string): never {
  if (error instanceof TRPCError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${context}: ${message}`,
  });
}
function validateRequired<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `${field} is required`,
    });
  }
  return value;
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
async function publishuserNotifPreferencesMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `platform.${action}` as any;
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
      txType: `platform_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `platform_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("platform", {
    ref,
    action,
    ...payload,
    timestamp: ts,
  }).catch(() => {});
}

export const userNotifPreferencesRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().min(1).max(500).optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const results = await database
          .select()
          .from(notification_channels)
          .orderBy(desc(auditLog.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(notification_channels);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch {
        return { data: [], total: 0, limit: 0, offset: 0 };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(notification_channels)
        .where(eq(auditLog.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
    const _totalRows = await database
      .select({ total: count() })
      .from(notification_channels);
    const totalResult = Array.isArray(_totalRows) ? _totalRows[0] : _totalRows;

    return {
      totalRecords: totalResult?.total ?? 0,
      lastUpdated: new Date().toISOString(),
    };
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(notification_channels)
        .orderBy(desc(auditLog.id))
        .limit(input.limit);

      return results;
    }),
  // FAIL LOUD: the preference mutations/queries below previously echoed
  // the input back (or returned hard-coded defaults) without persisting
  // anything.
  updateQuietHours: protectedProcedure
    .input(z.object({ start: z.string(), end: z.string() }))
    .mutation(async () => {
      throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Quiet-hours preferences is not wired to a real backend in this router; refusing to return a canned response.",
    });
    }),

  updateDigestMode: protectedProcedure
    .input(z.object({ mode: z.enum(["instant", "hourly", "daily"]) }))
    .mutation(async () => {
      throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Digest-mode preferences is not wired to a real backend in this router; refusing to return a canned response.",
    });
    }),

  bulkUpdate: protectedProcedure
    .input(
      z.object({
        categories: z.array(z.string()),
        channels: z.object({
          email: z.boolean(),
          sms: z.boolean(),
          push: z.boolean(),
          inApp: z.boolean(),
        }),
      })
    )
    .mutation(async () => {
      throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Bulk preference update is not wired to a real backend in this router; refusing to return a canned response.",
    });
    }),

  resetToDefaults: protectedProcedure.mutation(async () => {
    throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Preference reset is not wired to a real backend in this router; refusing to return a canned response.",
    });
  }),

  enableAllForChannel: protectedProcedure
    .input(z.object({ channel: z.string() }))
    .mutation(async () => {
      throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Channel preference update is not wired to a real backend in this router; refusing to return a canned response.",
    });
    }),

  getPreferences: protectedProcedure.query(async () => {
    // FAIL LOUD: previously returned a canned payload.
    throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "User notification preferences is not wired to a real backend in this router; refusing to return a canned response.",
    });
  }),

  categories: protectedProcedure.query(async () => {
    // FAIL LOUD: previously returned a canned payload.
    throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Notification category preferences is not wired to a real backend in this router; refusing to return a canned response.",
    });
  }),

  updateCategory: protectedProcedure
    .input(
      z.object({ categoryId: z.string().min(1).max(255), enabled: z.boolean() })
    )
    .mutation(async () => {
      throw new TRPCError({
      code: "NOT_IMPLEMENTED",
      message:
        "Category preference update is not wired to a real backend in this router; refusing to return a canned response.",
    });
    }),
});
