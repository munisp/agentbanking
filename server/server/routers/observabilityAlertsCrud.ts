// Sprint 87: Alert correlation, deduplication, escalation chains
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { observabilityAlerts } from "../../drizzle/schema";
import { eq, desc, and, count, sql } from "drizzle-orm";
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
  draft: ["scheduled", "generating"],
  scheduled: ["generating", "cancelled"],
  generating: ["completed", "failed"],
  completed: ["distributed", "archived"],
  distributed: ["acknowledged", "archived"],
  acknowledged: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["generating"],
  cancelled: [],
  archived: [],
};

const ESCALATION_CHAIN = [
  "on_call_engineer",
  "team_lead",
  "engineering_manager",
  "vp_engineering",
  "cto",
];
const DEDUP_WINDOW_MS = 300000; // 5 minutes

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "observabilityAlertsCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "observabilityAlertsCrud",
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
    resource: "observabilityAlertsCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "observabilityAlertsCrud",
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
      results.push(...(await Promise.all(ops.map(op => op()))));
      return results;
    });
  },
};

export const observabilityAlertsRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        status: z.string().optional(),
        severity: z.string().optional(),
        service: z.string().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.status)
          conditions.push(eq(observabilityAlerts.status, input.status));
        if (input.severity)
          conditions.push(eq(observabilityAlerts.severity, input.severity));
        if (input.service)
          conditions.push(eq(observabilityAlerts.service, input.service));
        const rows = await db
          .select()
          .from(observabilityAlerts)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(observabilityAlerts.createdAt))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(observabilityAlerts)
          .where(conditions.length ? and(...conditions) : undefined)
          .limit(100);
        return { items: rows, total };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .select()
          .from(observabilityAlerts)
          .where(eq(observabilityAlerts.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Alert not found",
          });
        return row;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  create: protectedProcedure
    .input(
      z.object({
        alertName: z.string(),
        service: z.string(),
        severity: z.enum(["critical", "warning", "info"]),
        metric: z.string(),
        threshold: z.string(),
        currentValue: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // ── Enforce STATUS_TRANSITIONS state machine ──
      if (typeof input === "object" && "status" in input) {
        const newStatus = (input as any).status as string;
        const currentStatus =
          ((input as any).currentStatus as string) || "pending";
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
          ? Number((input as any).amount)
          : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
      try {
        const db = (await getDb())!;
        // Deduplication: check for same alert within window
        const [recent] = await db
          .select()
          .from(observabilityAlerts)
          .where(
            and(
              eq(observabilityAlerts.alertName, input.alertName),
              eq(observabilityAlerts.service, input.service),
              eq(observabilityAlerts.status, "firing"),
              sql`created_at > NOW() - INTERVAL '5 minutes'`
            )
          )
          .limit(100);
        if (recent)
          await writeAuditLog({
            agentId:
              typeof ctx === "object" && ctx !== null && "user" in ctx
                ? (ctx.user?.id ?? 0)
                : 0,

            agentCode:
              typeof ctx === "object" && ctx !== null && "user" in ctx
                ? (ctx.user?.agentCode ?? "system")
                : "system",

            action: "MUTATION",

            resource: "observabilityAlertsCrud",

            resourceId:
              typeof input === "object" && input !== null && "id" in input
                ? String((input as any).id ?? "new")
                : "new",

            status: "success",

            metadata: { input: typeof input === "object" ? input : {} },
          });

        return {
          ...recent,
          deduplicated: true,
          message: "Alert deduplicated — existing alert still firing",
        };
        const [row] = await db
          .insert(observabilityAlerts)
          .values(input as any)
          .returning();
        const escalationLevel =
          input.severity === "critical"
            ? 2
            : input.severity === "warning"
              ? 1
              : 0;
        return {
          ...row,
          deduplicated: false,
          escalateTo: ESCALATION_CHAIN[escalationLevel],
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
  acknowledge: protectedProcedure
    .input(z.object({ id: z.number(), acknowledgedBy: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [alert] = await db
          .select()
          .from(observabilityAlerts)
          .where(eq(observabilityAlerts.id, input.id))
          .limit(100);
        if (!alert)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Alert not found",
          });
        if (alert.status !== "firing")
          throw new TRPCError({
            code: "PRECONDITION_FAILED",
            message: `Cannot acknowledge alert with status: ${alert.status}`,
          });
        const [row] = await db
          .update(observabilityAlerts)
          .set({
            status: "acknowledged",
            acknowledgedBy: input.acknowledgedBy,
            acknowledgedAt: new Date(),
          })
          .where(eq(observabilityAlerts.id, input.id))
          .returning();
        return { ...row, message: "Alert acknowledged" };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  resolve: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .update(observabilityAlerts)
          .set({ status: "resolved", resolvedAt: new Date() })
          .where(eq(observabilityAlerts.id, input.id))
          .returning();
        return { ...row, message: "Alert resolved" };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getSummary: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [stats] = await db
      .select({
        total: count(),
        firing: sql<number>`COUNT(*) FILTER (WHERE status = 'firing')`,
        acknowledged: sql<number>`COUNT(*) FILTER (WHERE status = 'acknowledged')`,
        resolved: sql<number>`COUNT(*) FILTER (WHERE status = 'resolved')`,
      })
      .from(observabilityAlerts)
      .limit(100);
    return { ...stats, escalationChain: ESCALATION_CHAIN };
  }),
});
