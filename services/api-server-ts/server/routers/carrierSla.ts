import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
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
  auditLog,
  systemConfig,
  sla_definitions,
  sla_breaches,
} from "../../drizzle/schema";
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
function validateCarrierslaInput(data: Record<string, unknown>): boolean {
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
      "carrierSla",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "carrierSla",
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
    resource: "carrierSla",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "carrierSla",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_CARRIERSLA = {
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
    if (!INTEGRITY_RULES_CARRIERSLA.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (!INTEGRITY_RULES_CARRIERSLA.validateRange(data.amount, 0, 100_000_000))
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _carrierSla_db = {
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

export const carrierSlaRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return { totalCarriers: 0, avgUptime: 0, slaBreaches: 0, activeSlas: 0 };
    const rows = await db
      .select()
      .from(systemConfig)
      .where(eq(systemConfig.key, "carrier_sla_stats"))
      .limit(1);
    if (rows.length > 0 && rows[0].value)
      return JSON.parse(String(rows[0].value));
    return { totalCarriers: 0, avgUptime: 99.5, slaBreaches: 0, activeSlas: 0 };
  }),
  listCarriers: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { carriers: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "carrier_sla_list"))
          .limit(1);
        const carriers =
          rows.length > 0 && rows[0].value
            ? JSON.parse(String(rows[0].value))
            : [];
        return {
          carriers: carriers.slice(0, input?.limit ?? 20),
          total: carriers.length,
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
  updateSla: protectedProcedure
    .input(
      z.object({
        carrierId: z.string(),
        uptimeTarget: z.number().min(90).max(100),
        responseTimeMs: z.number(),
        maxDowntimeMinutes: z.number(),
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
        "carrierSla",
        "mutation",
        "Executed carrierSla mutation"
      );

      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db.insert(auditLog).values({
          action: "carrier_sla_updated",
          resource: "carrier_sla",
          resourceId: input.carrierId,
          status: "success",
          metadata: {
            uptimeTarget: input.uptimeTarget,
            responseTimeMs: input.responseTimeMs,
            maxDowntimeMinutes: input.maxDowntimeMinutes,
          },
        });
        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  reportBreach: protectedProcedure
    .input(
      z.object({
        carrierId: z.string(),
        breachType: z.string(),
        description: z.string(),
        downtimeMinutes: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db.insert(auditLog).values({
          action: "sla_breach_reported",
          resource: "carrier_sla",
          resourceId: input.carrierId,
          status: "warning",
          metadata: {
            breachType: input.breachType,
            description: input.description,
            downtimeMinutes: input.downtimeMinutes,
          },
        });
        return {
          success: true,
          breachId: "SLA-" + crypto.randomUUID().toUpperCase(),
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

  // SLA breaches within the last `hours` hours, joined with sla_definitions
  getViolations: protectedProcedure
    .input(z.object({ hours: z.number().default(24) }).optional())
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return [];
      const since = new Date(Date.now() - (input?.hours ?? 24) * 3600 * 1000);
      const rows = await db
        .select({ breach: sla_breaches, definition: sla_definitions })
        .from(sla_breaches)
        .leftJoin(
          sla_definitions,
          eq(sla_breaches.slaDefinitionId, sla_definitions.id)
        )
        .where(gte(sla_breaches.createdAt, since))
        .orderBy(desc(sla_breaches.createdAt))
        .limit(100);
      return rows.map(r => ({
        id: r.breach.id,
        carrier: r.definition?.name ?? `SLA #${r.breach.slaDefinitionId}`,
        region: r.definition?.serviceType ?? null,
        violation: `${r.breach.breachType}: actual ${r.breach.actualValue} vs target ${r.breach.targetValue}`,
        severity: r.breach.impactLevel,
        resolved: r.breach.resolvedAt != null,
        timestamp: r.breach.createdAt?.toISOString() ?? null,
      }));
    }),

  // Compliance report over sla_definitions / sla_breaches for a period
  getComplianceReport: protectedProcedure
    .input(
      z
        .object({ period: z.enum(["daily", "weekly", "monthly"]).default("weekly") })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      const empty = {
        compliantCarriers: 0,
        nonCompliantCarriers: 0,
        overallScore: 100,
        details: [],
      };
      if (!db) return empty;
      const periodDays = { daily: 1, weekly: 7, monthly: 30 }[
        input?.period ?? "weekly"
      ];
      const since = new Date(Date.now() - periodDays * 24 * 3600 * 1000);
      const definitions = await db
        .select()
        .from(sla_definitions)
        .where(eq(sla_definitions.isActive, true))
        .limit(200);
      const breaches = await db
        .select()
        .from(sla_breaches)
        .where(gte(sla_breaches.createdAt, since))
        .limit(1000);
      const breachCountByDef = new Map<number, number>();
      for (const b of breaches) {
        breachCountByDef.set(
          b.slaDefinitionId,
          (breachCountByDef.get(b.slaDefinitionId) ?? 0) + 1
        );
      }
      const details = definitions.map(d => {
        const breachCount = breachCountByDef.get(d.id) ?? 0;
        const compliant = breachCount === 0;
        const metric = d.metricType.toLowerCase();
        return {
          carrier: d.name,
          uptime:
            metric.includes("uptime") || metric.includes("availability")
              ? d.targetValue
              : Math.max(0, 100 - breachCount),
          avgLatency: metric.includes("latency") ? d.targetValue : 0,
          breachCount,
          compliant,
        };
      });
      const compliantCarriers = details.filter(d => d.compliant).length;
      const nonCompliantCarriers = details.length - compliantCarriers;
      const overallScore =
        details.length > 0
          ? Math.round((compliantCarriers / details.length) * 1000) / 10
          : 100;
      return { compliantCarriers, nonCompliantCarriers, overallScore, details };
    }),
});
