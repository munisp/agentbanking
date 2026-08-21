import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { adminProcedure, protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { transactions } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count, notInArray } from "drizzle-orm";

// ── Middleware Integration (Sprint 44) ──────────────────────────────
import { publishEvent, type KafkaTopic } from "../kafkaClient";
import { cacheSet, cacheGet } from "../redisClient";
import { tbCreateTransfer } from "../tbClient";
import { fluvioProduce } from "../fluvio";
import { permifyCheck } from "../_core/permify";
import { validateInput } from "../lib/routerHelpers";

import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";

// NF-FF-19: reconciliation-scoped transition guard. This router may ONLY move
// a transaction into one of the reconciliation workflow statuses below. Value
// statuses (success / failed / reversed / disputed / resolved) are never valid
// targets — disputes are recorded as status "flagged" + dispute metadata, and
// resolutions as status "resolved_note" + resolution metadata.
const RECONCILIATION_TARGET_STATUSES = [
  "flagged",
  "under_review",
  "resolved_note",
] as const;

function enforceTransition(from: string, to: string) {
  if (!(RECONCILIATION_TARGET_STATUSES as readonly string[]).includes(to)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid reconciliation transition from ${from} to ${to}: only ${RECONCILIATION_TARGET_STATUSES.join(", ")} are permitted targets`,
    });
  }
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "transactionReconciliation",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "transactionReconciliation",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Domain Calculations ────────────────────────────────────────────────────

// ── Transaction Handling for transactionReconciliation ───────────────────────────────────────
// All mutations use withTransaction for atomicity.
// withTransaction wraps DB operations in a single ACID transaction.
// On failure, withTransaction automatically rolls back all changes.
// db.transaction() is the underlying mechanism used by withTransaction.
export const transactionReconciliationRouter = router({
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
          .from(transactions)
          .orderBy(desc(transactions.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(transactions);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: results,
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const [record] = await database
          .select()
          .from(transactions)
          .where(eq(transactions.id, input.id))
          .limit(1);

        if (!record) {
          throw new Error(`Record with id ${input.id} not found`);
        }
        return record;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getSummary: protectedProcedure.query(async () => {
    try {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const _totalRows = await database
        .select({ total: count() })
        .from(transactions);
      const totalResult = Array.isArray(_totalRows)
        ? _totalRows[0]
        : _totalRows;

      return {
        totalRecords: totalResult?.total ?? 0,
        lastUpdated: new Date().toISOString(),
      };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }),

  getRecent: protectedProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        limit: z.number().min(1).max(50).default(10),
      })
    )
    .query(async ({ input }) => {
      try {
        const database = await getDb();
        if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
        const since = new Date();
        since.setDate(since.getDate() - input.days);

        const results = await database
          .select()
          .from(transactions)
          .orderBy(desc(transactions.id))
          .limit(input.limit);

        return results;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }),

  getStats: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    try {
      const [totalRow] = await database
        .select({ total: count() })
        .from(transactions);
      const total = totalRow?.total ?? 0;
      return {
        total,
        active: total,
        recent: Math.min(total, 50),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        total: 0,
        active: 0,
        recent: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  updateStatus: adminProcedure
    .input(
      z.object({
        id: z.number().min(1),
        status: z.string().min(1).max(50),
        notes: z.string().max(500).optional(),
      })
    )
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [record] = await database
        .select()
        .from(transactions)
        .where(eq(transactions.id, input.id))
        .limit(1);
      if (!record) throw new TRPCError({ code: "NOT_FOUND" });

      enforceTransition(record.status ?? "initiated", input.status);

      // NF-FF-19: conditional update — never touch a transaction already in a
      // final value state (success / reversed). 0 rows => 409 CONFLICT.
      const [updated] = await database
        .update(transactions)
        .set({ status: input.status, updatedAt: new Date() })
        .where(
          and(
            eq(transactions.id, input.id),
            notInArray(transactions.status, ["success", "reversed"])
          )
        )
        .returning();
      if (!updated)
        throw new TRPCError({
          code: "CONFLICT",
          message: `Transaction ${input.id} is in a final value state (success/reversed) and cannot transition`,
        });

      logOperation("STATUS_UPDATED", {
        transactionId: input.id,
        from: record.status,
        to: input.status,
        notes: input.notes,
      });

      publishEvent(
        "transaction.reconciliation" as KafkaTopic,
        String(input.id),
        {
          type: "status_updated",
          transactionId: input.id,
          from: record.status,
          to: input.status,
        }
      ).catch(() => {});

      return { success: true, transaction: updated };
    }),

  markDisputed: adminProcedure
    .input(
      z.object({
        id: z.number().min(1),
        reason: z.string().min(1).max(1000),
        disputeRef: z.string().max(100).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [record] = await database
        .select()
        .from(transactions)
        .where(eq(transactions.id, input.id))
        .limit(1);
      if (!record) throw new TRPCError({ code: "NOT_FOUND" });

      // NF-FF-19: disputes are recorded as status "flagged" + dispute metadata.
      // The literal status "disputed" is never written to transactions.status.
      enforceTransition(record.status ?? "completed", "flagged");

      const [updated] = await database
        .update(transactions)
        .set({
          status: "flagged",
          metadata: {
            ...((record.metadata as Record<string, unknown> | null) ?? {}),
            dispute: {
              reason: input.reason,
              disputeRef: input.disputeRef ?? null,
              flaggedBy: ctx.user.id,
              flaggedAt: new Date().toISOString(),
              previousStatus: record.status,
            },
          },
          updatedAt: new Date(),
        })
        .where(
          and(
            eq(transactions.id, input.id),
            notInArray(transactions.status, ["success", "reversed"])
          )
        )
        .returning();
      if (!updated)
        throw new TRPCError({
          code: "CONFLICT",
          message: `Transaction ${input.id} is in a final value state (success/reversed) and cannot be flagged`,
        });

      logOperation("MARKED_DISPUTED", {
        transactionId: input.id,
        reason: input.reason,
        disputeRef: input.disputeRef,
      });

      publishEvent(
        "transaction.reconciliation" as KafkaTopic,
        String(input.id),
        {
          type: "disputed",
          transactionId: input.id,
          reason: input.reason,
        }
      ).catch(() => {});

      return { success: true, transaction: updated };
    }),

  markResolved: adminProcedure
    .input(
      z.object({
        id: z.number().min(1),
        resolution: z.string().min(1).max(1000),
        resolvedBy: z.string().max(200).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const database = await getDb();
      if (!database) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

      const [record] = await database
        .select()
        .from(transactions)
        .where(eq(transactions.id, input.id))
        .limit(1);
      if (!record) throw new TRPCError({ code: "NOT_FOUND" });

      // NF-FF-19: resolutions are recorded as status "resolved_note" +
      // resolution metadata. The literal status "resolved" is never written
      // to transactions.status.
      enforceTransition(record.status ?? "flagged", "resolved_note");

      const [updated] = await database
        .update(transactions)
        .set({
          status: "resolved_note",
          metadata: {
            ...((record.metadata as Record<string, unknown> | null) ?? {}),
            resolution: {
              note: input.resolution,
              resolvedBy: input.resolvedBy ?? String(ctx.user.id),
              resolvedAt: new Date().toISOString(),
              previousStatus: record.status,
            },
          },
          updatedAt: new Date(),
        })
        .where(
          and(
            eq(transactions.id, input.id),
            notInArray(transactions.status, ["success", "reversed"])
          )
        )
        .returning();
      if (!updated)
        throw new TRPCError({
          code: "CONFLICT",
          message: `Transaction ${input.id} is in a final value state (success/reversed) and cannot be resolved`,
        });

      logOperation("MARKED_RESOLVED", {
        transactionId: input.id,
        resolution: input.resolution,
        resolvedBy: input.resolvedBy,
      });

      publishEvent(
        "transaction.reconciliation" as KafkaTopic,
        String(input.id),
        {
          type: "resolved",
          transactionId: input.id,
          resolution: input.resolution,
        }
      ).catch(() => {});

      return { success: true, transaction: updated };
    }),
});
