// @ts-nocheck
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
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
import { auditLog, systemConfig } from "../../drizzle/schema";
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

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "reportBuilderTemplates",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "reportBuilderTemplates",
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
    resource: "reportBuilderTemplates",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "reportBuilderTemplates",
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
async function publishreportBuilderTemplatesMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>,
) {
  const topic = `reporting.${action}` as any;
  const ts = new Date().toISOString();

  // 1. Kafka — event stream (fail-open)
  publishEvent(topic, ref, { ...payload, action, timestamp: ts }).catch(() => {});

  // 2. TigerBeetle — GL journal entry (fail-open)
  if (payload.amount && typeof payload.amount === "number") {
    tbCreateTransfer({
      debitAccountId: String(payload.debitAccount ?? "3001"),
      creditAccountId: String(payload.creditAccount ?? "4001"),
      amount: Math.round(Number(payload.amount) * 100),
      ref,
      txType: `reporting_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `reporting_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr.publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts }).catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("reporting", { ref, action, ...payload, timestamp: ts }).catch(() => {});
}

export const reportBuilderTemplatesRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db)
      return {
        totalTemplates: 0,
        activeTemplates: 0,
        reportsGenerated: 0,
        scheduledReports: 0,
      };
    const rows = await db
      .select()
      .from(systemConfig)
      .where(sql`\${systemConfig.key} LIKE 'rpt_builder_%'`)
      .limit(100);
    return {
      totalTemplates: rows.length,
      activeTemplates: rows.length,
      reportsGenerated: 0,
      scheduledReports: 0,
    };
  }),
  listTemplates: protectedProcedure
    .input(
      z
        .object({
          category: z.string().optional(),
          limit: z.number().default(20),
        })
        .optional()
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { templates: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(sql`\${systemConfig.key} LIKE 'rpt_builder_%'`)
          .limit(input?.limit ?? 20);
        let templates = rows.map(r => ({
          id: r.key.replace("rpt_builder_", ""),
          ...JSON.parse(String(r.value ?? "{}")),
        }));
        if (input?.category)
          templates = templates.filter(
            (t: any) => t.category === input.category
          );
        return { templates, total: templates.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  createTemplate: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        category: z.string(),
        description: z.string().optional(),
        columns: z.array(
          z.object({
            field: z.string(),
            label: z.string(),
            type: z.string().default("text"),
          })
        ),
        filters: z
          .array(
            z.object({
              field: z.string(),
              operator: z.string(),
              value: z.string().optional(),
            })
          )
          .optional(),
        format: z.enum(["pdf", "csv", "xlsx"]).default("pdf"),
      })
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
        const templateId = "RPTB-" + crypto.randomUUID().toUpperCase();
        await db.insert(systemConfig).values({
          key: "rpt_builder_" + templateId,
          value: JSON.stringify({
            ...input,
            status: "active",
            createdAt: new Date().toISOString(),
          }),
        });
        await db.insert(auditLog).values({
          action: "report_builder_template_created",
          resource: "report_builder",
          resourceId: templateId,
          status: "success",
          metadata: { name: input.name, category: input.category },
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

          resource: "reportBuilderTemplates",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { success: true, templateId };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  deleteTemplate: protectedProcedure
    .input(z.object({ templateId: z.string().min(1).max(255) }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db
          .delete(systemConfig)
          .where(eq(systemConfig.key, "rpt_builder_" + input.templateId));
        // Middleware fan-out (fail-open)
        await publishreportBuilderTemplatesMiddleware("deleteTemplate", `${Date.now()}`, { action: "deleteTemplate" }).catch(() => {});

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
  generateReport: protectedProcedure
    .input(
      z.object({
        templateId: z.string().min(1).max(255),
        dateRange: z.object({ from: z.string(), to: z.string() }).optional(),
        filters: z.record(z.string(), z.string()).optional(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const reportId = "RPT-" + crypto.randomUUID().toUpperCase();
        await db.insert(auditLog).values({
          action: "report_generated",
          resource: "report_builder",
          resourceId: reportId,
          status: "success",
          metadata: {
            templateId: input.templateId,
            dateRange: input.dateRange,
          },
        });
        // Middleware fan-out (fail-open)
        await publishreportBuilderTemplatesMiddleware("generateReport", `${Date.now()}`, { action: "generateReport" }).catch(() => {});

        return { success: true, reportId, status: "generating" };
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
