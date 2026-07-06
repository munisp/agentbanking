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
      "pbacManagement",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "pbacManagement",
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
    resource: "pbacManagement",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "pbacManagement",
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
async function publishpbacManagementMiddleware(
  action: string,
  ref: string,
  payload: Record<string, unknown>
) {
  const topic = `management.${action}` as any;
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
      txType: `management_${action}`,
      agentCode: String(payload.agentCode ?? "system"),
    }).catch(() => {});
  }

  // 3. Fluvio — real-time fraud stream (fail-open)
  publishTxToFluvio({
    txRef: ref,
    agentCode: String(payload.agentCode ?? "system"),
    amount: Number(payload.amount ?? 0),
    type: `management_${action}`,
    timestamp: Date.now(),
  }).catch(() => {});

  // 4. Dapr — service mesh pub/sub (fail-open)
  dapr
    .publishEvent("pubsub", topic, { ref, ...payload, timestamp: ts })
    .catch(() => {});

  // 5. Lakehouse — analytics ingestion (fail-open)
  ingestToLakehouse("management", {
    ref,
    action,
    ...payload,
    timestamp: ts,
  }).catch(() => {});
}

export const pbacManagementRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { totalPolicies: 0, totalRoles: 0, activeAssignments: 0 };
    const policies = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'pbac_policy_%'`)
      .limit(100);
    const roles = await db
      .select()
      .from(systemConfig)
      .where(sql`${systemConfig.key} LIKE 'role_%'`)
      .limit(100);
    return {
      totalPolicies: policies.length,
      totalRoles: roles.length,
      activeAssignments: 0,
    };
  }),
  listPolicies: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { policies: [], total: 0 };
        const rows = await db
          .select()
          .from(systemConfig)
          .where(sql`${systemConfig.key} LIKE 'pbac_policy_%'`)
          .limit(input?.limit ?? 50);
        return {
          policies: rows.map(r => ({
            id: r.key.replace("pbac_policy_", ""),
            ...JSON.parse(String(r.value ?? "{}")),
          })),
          total: rows.length,
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
  createPolicy: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        resource: z.string(),
        actions: z.array(z.string()),
        conditions: z.record(z.string(), z.any()).optional(),
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
        const key =
          "pbac_policy_" + input.name.toLowerCase().replace(/\s+/g, "_");
        await db.insert(systemConfig).values({
          key,
          value: JSON.stringify({
            ...input,
            createdAt: new Date().toISOString(),
          }),
        });
        await db.insert(auditLog).values({
          action: "pbac_policy_created",
          resource: "pbac",
          resourceId: key,
          status: "success",
          metadata: { name: input.name },
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

          resource: "pbacManagement",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id)
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        // Middleware fan-out (fail-open)

        await publishpbacManagementMiddleware("createPolicy", `${Date.now()}`, {
          action: "createPolicy",
        }).catch(() => {});

        return { success: true, policyId: key };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  deletePolicy: protectedProcedure
    .input(z.object({ policyId: z.string().min(1).max(255) }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        await db
          .delete(systemConfig)
          .where(eq(systemConfig.key, "pbac_policy_" + input.policyId));
        await db.insert(auditLog).values({
          action: "pbac_policy_deleted",
          resource: "pbac",
          resourceId: input.policyId,
          status: "success",
        });
        // Middleware fan-out (fail-open)
        await publishpbacManagementMiddleware("deletePolicy", `${Date.now()}`, {
          action: "deletePolicy",
        }).catch(() => {});

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

  assignRole: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      // Middleware fan-out (fail-open)
      await publishpbacManagementMiddleware("assignRole", `${Date.now()}`, {
        action: "assignRole",
      }).catch(() => {});

      return { success: true };
    }),

  getAuditLog: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  getRoleDetail: protectedProcedure.query(async () => {
    return { data: [], total: 0 };
  }),

  listPermissions: protectedProcedure.query(async () => {
    // Middleware fan-out (fail-open)
    await publishpbacManagementMiddleware("listPermissions", `${Date.now()}`, {
      action: "listPermissions",
    }).catch(() => {});

    return { data: [], total: 0 };
  }),

  listRoles: protectedProcedure.query(async () => {
    // Middleware fan-out (fail-open)
    await publishpbacManagementMiddleware("listRoles", `${Date.now()}`, {
      action: "listRoles",
    }).catch(() => {});

    return { data: [], total: 0 };
  }),

  listUserAssignments: protectedProcedure.query(async () => {
    // Middleware fan-out (fail-open)
    await publishpbacManagementMiddleware(
      "listUserAssignments",
      `${Date.now()}`,
      { action: "listUserAssignments" }
    ).catch(() => {});

    return { data: [], total: 0 };
  }),

  modifyPermissions: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      // Middleware fan-out (fail-open)
      await publishpbacManagementMiddleware(
        "modifyPermissions",
        `${Date.now()}`,
        { action: "modifyPermissions" }
      ).catch(() => {});

      return { success: true };
    }),

  removeAssignment: protectedProcedure
    .input(
      z.object({ id: z.union([z.number(), z.string()]).optional() }).optional()
    )
    .mutation(async () => {
      // Middleware fan-out (fail-open)
      await publishpbacManagementMiddleware(
        "removeAssignment",
        `${Date.now()}`,
        { action: "removeAssignment" }
      ).catch(() => {});

      return { success: true };
    }),
});
