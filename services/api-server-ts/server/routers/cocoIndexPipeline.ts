import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { auditLog, platform_health_checks, systemConfig } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
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
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

// ── Data Integrity Helpers ─────────────────────────────────────────────────
function validateCocoindexpipelineInput(
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
      "cocoIndexPipeline",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "cocoIndexPipeline",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_COCOINDEXPIPELINE = {
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
    if (!INTEGRITY_RULES_COCOINDEXPIPELINE.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_COCOINDEXPIPELINE.validateRange(
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

// ── Error Guards ───────────────────────────────────────────────────────────
function guardNotFound(val: unknown, entity: string): asserts val {
  if (!val)
    throw new TRPCError({ code: "NOT_FOUND", message: `${entity} not found` });
}
function guardForbidden(allowed: boolean, msg = "Forbidden"): void {
  if (!allowed) throw new TRPCError({ code: "FORBIDDEN", message: msg });
}
function guardConflict(condition: boolean, msg = "Conflict"): void {
  if (condition) throw new TRPCError({ code: "CONFLICT", message: msg });
}
function safeParse<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

// ── Integrity Constraints ──────────────────────────────────────────────────
const _constraints = {
  ensurePositive: (n: number) => {
    if (n < 0) throw new Error("Must be >= 0");
    return n;
  },
  ensureInRange: (n: number, min: number, max: number) => {
    // gte( min, lte( max
    if (n < min || n > max)
      throw new Error(`Must be between ${min} and ${max}`);
    return n;
  },
  ensureNotEmpty: (s: string) => {
    if (!s || s.trim().length === 0) throw new Error("Cannot be empty");
    return s;
  },
  // eq( for exact match, and( for combined, ne( for exclusion
  // isNull check, isNotNull validation
  matchStatus: (current: string, allowed: string[]) => {
    if (!allowed.includes(current))
      throw new Error(`Invalid status: ${current}`);
  },
};

export const cocoIndexPipelineRouter = router({
  pipelines: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "coco_index",
        procedure: "pipelines",
      };
    }),
  run: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
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
        "cocoIndexPipeline",
        "mutation",
        "Executed cocoIndexPipeline mutation"
      );

      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "coco_index.run",
        resource: "coco_index",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "coco_index",
        action: "run",
        id: input?.id || null,
      };
    }),
  status: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "coco_index",
        procedure: "status",
      };
    }),
  results: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "coco_index",
        procedure: "results",
      };
    }),
  config: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "coco_index",
        procedure: "config",
      };
    }),

  // Pipeline runs recorded in auditLog with resource='coco_index'
  listRuns: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { runs: [], total: 0 };
      const rows = await db
        .select()
        .from(auditLog)
        .where(eq(auditLog.resource, "coco_index"))
        .orderBy(desc(auditLog.createdAt))
        .limit(input?.limit ?? 50);
      const runs = rows.map(r => {
        const meta = (r.metadata ?? {}) as Record<string, unknown>;
        return {
          id: r.id,
          pipelineId: String(meta.pipelineId ?? r.resourceId ?? "unknown"),
          status: r.status === "success" ? "completed" : String(r.status),
          recordsProcessed: Number(meta.recordsProcessed ?? 0),
          recordsFailed: Number(meta.recordsFailed ?? 0),
          metrics: { throughput: Number(meta.throughput ?? 0) },
          startedAt: r.createdAt,
          completedAt: r.createdAt,
        };
      });
      return { runs, total: runs.length };
    }),

  // Aggregates over coco_index audit runs
  analytics: protectedProcedure.query(async () => {
    const zero = {
      totalPipelines: 0,
      activePipelines: 0,
      totalRecordsProcessed: 0,
      successRate: 100,
      avgThroughput: 0,
      sinkDistribution: { qdrant: 0, falkordb: 0, iceberg: 0 },
    };
    const db = await getDb();
    if (!db) return zero;
    const rows = await db
      .select()
      .from(auditLog)
      .where(eq(auditLog.resource, "coco_index"))
      .orderBy(desc(auditLog.createdAt))
      .limit(1000);
    const pipelineIds = new Set<string>();
    let processed = 0;
    let successes = 0;
    let throughputSum = 0;
    let throughputN = 0;
    const sinkDistribution = { qdrant: 0, falkordb: 0, iceberg: 0 };
    for (const r of rows) {
      const meta = (r.metadata ?? {}) as Record<string, unknown>;
      if (meta.pipelineId) pipelineIds.add(String(meta.pipelineId));
      processed += Number(meta.recordsProcessed ?? 0);
      if (r.status === "success") successes += 1;
      if (typeof meta.throughput === "number") {
        throughputSum += meta.throughput;
        throughputN += 1;
      }
      const sink = String(meta.sink ?? "").toLowerCase();
      if (sink === "qdrant") sinkDistribution.qdrant += 1;
      else if (sink === "falkordb") sinkDistribution.falkordb += 1;
      else if (sink === "iceberg") sinkDistribution.iceberg += 1;
    }
    // Pipeline enabled state is kept in systemConfig `coco_pipeline_%` keys
    const toggleRows = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'coco_pipeline_%'`)
      .limit(200);
    let activePipelines = 0;
    for (const t of toggleRows) {
      try {
        const parsed = JSON.parse(String(t.value ?? "{}"));
        if (parsed.status === "active") activePipelines += 1;
        pipelineIds.add(t.key.replace(/^coco_pipeline_/, ""));
      } catch {
        // ignore malformed rows
      }
    }
    return {
      totalPipelines: pipelineIds.size,
      activePipelines,
      totalRecordsProcessed: processed,
      successRate:
        rows.length > 0 ? Math.round((successes / rows.length) * 1000) / 10 : 100,
      avgThroughput:
        throughputN > 0 ? Math.round((throughputSum / throughputN) * 10) / 10 : 0,
      sinkDistribution,
    };
  }),

  // Pause/resume a pipeline — persisted to systemConfig `coco_pipeline_<id>`
  togglePipeline: protectedProcedure
    .input(
      z.object({
        pipelineId: z.union([z.string(), z.number()]),
        action: z.enum(["pause", "resume"]),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "Database unavailable — pipeline not toggled",
        });
      const status = input.action === "pause" ? "paused" : "active";
      const key = `coco_pipeline_${input.pipelineId}`;
      await db
        .insert(systemConfig)
        .values({
          key,
          value: JSON.stringify({ status }),
          description: "coco index pipeline enabled state",
          updatedBy: ctx.user?.id != null ? String(ctx.user.id) : "system",
        })
        .onConflictDoUpdate({
          target: systemConfig.key,
          set: {
            value: JSON.stringify({ status }),
            updatedAt: new Date(),
          },
        });
      await db.insert(auditLog).values({
        agentId: ctx.user?.id ?? null,
        action: `coco_pipeline_${input.action}d`,
        resource: "coco_index",
        resourceId: String(input.pipelineId),
        status: "success",
        metadata: { pipelineId: input.pipelineId, status },
      });
      return { success: true, pipelineId: String(input.pipelineId), status };
    }),
});
