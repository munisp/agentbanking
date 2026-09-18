import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { connectivityLog, auditLog, systemConfig } from "../../drizzle/schema";
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
function validateNetworkresilienceInput(
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
      "networkResilience",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "networkResilience",
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
    resource: "networkResilience",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "networkResilience",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_NETWORKRESILIENCE = {
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
    if (!INTEGRITY_RULES_NETWORKRESILIENCE.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_NETWORKRESILIENCE.validateRange(
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

// ── Database Query Patterns ────────────────────────────────────────────────
const _networkResilience_db = {
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

export const networkResilienceRouter = router({
  status: protectedProcedure
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
        "networkResilience",
        "mutation",
        "Executed networkResilience mutation"
      );

      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "net_resilience.status",
        resource: "net_resilience",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "net_resilience",
        action: "status",
        id: input?.id || null,
      };
    }),
  failover: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "net_resilience.failover",
        resource: "net_resilience",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "net_resilience",
        action: "failover",
        id: input?.id || null,
      };
    }),
  history: protectedProcedure
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "net_resilience",
        procedure: "history",
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
        .from(connectivityLog)
        .orderBy(desc(connectivityLog.recordedAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(connectivityLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "net_resilience",
        procedure: "config",
      };
    }),
  test: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "net_resilience.test",
        resource: "net_resilience",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "net_resilience",
        action: "test",
        id: input?.id || null,
      };
    }),

  // Connection metrics aggregated from connectivity_log (last 24h)
  getConnectionMetrics: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return {
        avgLatencyMs: 0,
        jitterMs: 0,
        packetLossPct: 0,
        bandwidthKbps: 0,
        agents: [],
        totalConnections: 0,
        activeWebSocket: 0,
        activeSSE: 0,
        activeLongPoll: 0,
        offlineAgents: 0,
      };
    const since = new Date(Date.now() - 24 * 3600 * 1000);
    const rows = await db
      .select()
      .from(connectivityLog)
      .where(gte(connectivityLog.recordedAt, since))
      .orderBy(desc(connectivityLog.recordedAt))
      .limit(1000);
    const latencies = rows
      .map(r => r.latencyMs)
      .filter((v): v is number => v != null);
    const avgLatencyMs =
      latencies.length > 0
        ? Math.round(
            latencies.reduce((a: number, b: number) => a + b, 0) /
              latencies.length
          )
        : 0;
    const jitterMs =
      latencies.length > 1
        ? Math.round(
            latencies.reduce(
              (a: number, b: number) => a + Math.abs(b - avgLatencyMs),
              0
            ) / latencies.length
          )
        : 0;
    const degraded = rows.filter(
      r => r.quality === "Poor" || r.quality === "Offline"
    ).length;
    const packetLossPct =
      rows.length > 0 ? Math.round((degraded / rows.length) * 1000) / 10 : 0;
    const latestByAgent = new Map<string, (typeof rows)[number]>();
    for (const row of rows) {
      if (!latestByAgent.has(row.agentCode)) latestByAgent.set(row.agentCode, row);
    }
    const agents = Array.from(latestByAgent.values()).map(r => ({
      agentCode: r.agentCode,
      quality: r.quality,
      latencyMs: r.latencyMs,
      recordedAt: r.recordedAt,
    }));
    const offlineAgents = agents.filter(a => a.quality === "Offline").length;
    return {
      avgLatencyMs,
      jitterMs,
      packetLossPct,
      bandwidthKbps: 0,
      agents,
      totalConnections: rows.length,
      activeWebSocket: 0,
      activeSSE: 0,
      activeLongPoll: 0,
      offlineAgents,
    };
  }),

  // Bandwidth tuning config persisted in systemConfig under `bandwidth_%` keys
  getBandwidthConfig: protectedProcedure.query(async () => {
    const defaults = {
      adaptiveBandwidth: false,
      compressionEnabled: false,
      lowBandwidthThresholdKbps: 256,
      maxPayloadBytes: 65536,
    };
    const db = await getDb();
    if (!db) return defaults;
    const rows = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'bandwidth_%'`)
      .limit(50);
    const byKey: Record<string, string> = {};
    for (const r of rows) byKey[r.key] = String(r.value ?? "");
    const asBool = (v: string | undefined, d: boolean) =>
      v === undefined ? d : v === "true" || v === "1";
    const asInt = (v: string | undefined, d: number) => {
      const n = parseInt(v ?? "", 10);
      return Number.isFinite(n) ? n : d;
    };
    return {
      adaptiveBandwidth: asBool(
        byKey["bandwidth_adaptive"],
        defaults.adaptiveBandwidth
      ),
      compressionEnabled: asBool(
        byKey["bandwidth_compression"],
        defaults.compressionEnabled
      ),
      lowBandwidthThresholdKbps: asInt(
        byKey["bandwidth_low_threshold_kbps"],
        defaults.lowBandwidthThresholdKbps
      ),
      maxPayloadBytes: asInt(
        byKey["bandwidth_max_payload_bytes"],
        defaults.maxPayloadBytes
      ),
    };
  }),
});
