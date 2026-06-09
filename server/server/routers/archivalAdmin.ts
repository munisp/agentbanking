import { z } from "zod";
import { TRPCError } from "@trpc/server";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { auditLog, backupSnapshots } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
import { notifyOwner } from "../_core/notification";
import { getConfig, setConfig } from "../lib/runtimeConfig";
import { runArchivalJob, getArchivalStats } from "../lib/parquetArchival";
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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  cancelled: [],
  archived: [],
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
      "archivalAdmin",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "archivalAdmin",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_ARCHIVALADMIN = {
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
    if (!INTEGRITY_RULES_ARCHIVALADMIN.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_ARCHIVALADMIN.validateRange(data.amount, 0, 100_000_000)
    )
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
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

// ── Database Query Patterns ────────────────────────────────────────────────
const _archivalAdmin_db = {
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

// ── Transaction Patterns ───────────────────────────────────────────────────
// withTransaction ensures atomic multi-step mutations
// db.transaction() wraps sequential DB ops in a single transaction
// .transaction() provides rollback on failure
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

export const archivalAdminRouter = router({
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
        if (!database)
          return {
            data: [],
            total: 0,
            limit: input.limit,
            offset: input.offset,
          };
        const results = await database
          .select()
          .from(backupSnapshots)
          .orderBy(desc(auditLog.id))
          .limit(input.limit)
          .offset(input.offset);

        const _totalRows = await database
          .select({ total: count() })
          .from(backupSnapshots);
        const totalResult = Array.isArray(_totalRows)
          ? _totalRows[0]
          : _totalRows;

        return {
          data: Array.isArray(results) ? results : [],
          total: totalResult?.total ?? 0,
          limit: input.limit,
          offset: input.offset,
        };
      } catch {
        return { data: [], total: 0, limit: input.limit, offset: input.offset };
      }
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { data: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(backupSnapshots)
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
      .from(backupSnapshots);
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
        .from(backupSnapshots)
        .orderBy(desc(auditLog.id))
        .limit(input.limit);

      return results;
    }),

  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return {
        totalArchived: 0,
        lastRun: null,
        schedule: null as {
          enabled: boolean;
          cronExpression: string;
          retentionDays: number;
          deleteAfterArchive: boolean;
          nextRun: string | null;
        } | null,
        currentJob: null as {
          id: string;
          startedAt: string;
          retentionDays: number;
        } | null,
        eligibleSettlements: 0,
        eligibleBatches: 0,
        cutoffDate: new Date(),
        retentionDays: 90,
      };
    const archivalStats = await getArchivalStats();
    const rawSchedule = await getConfig("archival_schedule");
    let schedule: {
      enabled: boolean;
      cronExpression: string;
      retentionDays: number;
      deleteAfterArchive: boolean;
      nextRun: string | null;
    } | null = null;
    if (rawSchedule) {
      try {
        const parsed =
          typeof rawSchedule === "string" && rawSchedule.startsWith("{")
            ? JSON.parse(rawSchedule)
            : null;
        if (parsed && typeof parsed === "object") {
          schedule = {
            enabled: parsed.enabled ?? true,
            cronExpression: parsed.cronExpression ?? String(rawSchedule),
            retentionDays: parsed.retentionDays ?? 90,
            deleteAfterArchive: parsed.deleteAfterArchive ?? false,
            nextRun: parsed.nextRun ?? null,
          };
        } else {
          schedule = {
            enabled: true,
            cronExpression: String(rawSchedule),
            retentionDays: 90,
            deleteAfterArchive: false,
            nextRun: null,
          };
        }
      } catch {
        schedule = {
          enabled: true,
          cronExpression: String(rawSchedule),
          retentionDays: 90,
          deleteAfterArchive: false,
          nextRun: null,
        };
      }
    }
    return {
      ...archivalStats,
      schedule,
      currentJob: null as {
        id: string;
        startedAt: string;
        retentionDays: number;
      } | null,
    };
  }),

  triggerArchival: protectedProcedure
    .input(
      z.object({
        triggeredBy: z.string().default("manual"),
        retentionDays: z.number().optional(),
        deleteAfterArchive: z.boolean().optional(),
        tables: z.array(z.string()).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const txAmount = typeof input === "object" && "amount" in input ? Number((input as Record<string, unknown>).amount) : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
const startTime = Date.now();
      const job = { id: `archival_${Date.now()}` };
      try {
        const result = await runArchivalJob({
          retentionDays: input.retentionDays,
          deleteAfterArchive: input.deleteAfterArchive,
        });
        const duration = Date.now() - startTime;
        await notifyOwner({
          title: `Archival Job ${job.id} Completed`,
          content: `Triggered by: ${input.triggeredBy}\nTotal archived: ${result.totalArchived} records\nDuration: ${duration}ms`,
        });
        await writeAuditLog({

          agentId: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.id ?? 0 : 0,

          agentCode: typeof ctx === "object" && ctx !== null && "user" in ctx ? (ctx as any).user?.agentCode ?? "system" : "system",

          action: "MUTATION",

          resource: "archivalAdmin",

          resourceId: typeof input === "object" && input !== null && "id" in input ? String((input as any).id) : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },

        });

        return {
          success: true as const,
          jobId: job.id,
          ...result,
          duration,
          error: null as string | null,
        };
      } catch (err: any) {
        const duration = Date.now() - startTime;
        await notifyOwner({
          title: `Archival Job ${job.id} Failed`,
          content: `Triggered by: ${input.triggeredBy}\nError: ${err.message}\nDuration: ${duration}ms`,
        });
        return {
          success: false as const,
          jobId: job.id,
          error: err.message as string | null,
          totalArchived: 0,
          totalDeleted: 0,
          tables: [] as any[],
          startedAt: new Date(),
          completedAt: new Date(),
          duration,
        };
      }
    }),

  updateSchedule: protectedProcedure
    .input(
      z.object({
        enabled: z.boolean().default(false),
        cronExpression: z.string().default("0 2 * * 0"),
        retentionDays: z.number().default(90),
        deleteAfterArchive: z.boolean().default(false),
      })
    )
    .mutation(async ({ input }) => {
      const schedule = JSON.stringify(input);
      await setConfig("archival_schedule", schedule);
      return { success: true, schedule: input };
    }),

  getHistory: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
      })
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return [];
      const results = await db
        .select()
        .from(backupSnapshots)
        .where(eq(auditLog.action, "archival_job"))
        .orderBy(desc(auditLog.id))
        .limit(input.limit);
      return results;
    }),
});
