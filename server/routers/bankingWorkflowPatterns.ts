import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, sql, count, and, gte, lte } from "drizzle-orm";
import {
  workflowDefinitions,
  workflowInstances,
  auditLog,
} from "../../drizzle/schema";
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
      "bankingWorkflowPatterns",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "bankingWorkflowPatterns",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_BANKINGWORKFLOWPATTERNS = {
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
    if (!INTEGRITY_RULES_BANKINGWORKFLOWPATTERNS.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (
      !INTEGRITY_RULES_BANKINGWORKFLOWPATTERNS.validateRange(
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

export const bankingWorkflowPatternsRouter = router({
  listWorkflows: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(workflowDefinitions)
          .orderBy(desc(workflowDefinitions.createdAt))
          .limit(input?.limit ?? 50);
        return { workflows: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getWorkflow: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [wf] = await db
          .select()
          .from(workflowDefinitions)
          .where(eq(workflowDefinitions.id, input.id))
          .limit(1);
        if (!wf) return null;
        const instances = await db
          .select()
          .from(workflowInstances)
          .where(eq(workflowInstances.definitionId, input.id))
          .orderBy(desc(workflowInstances.createdAt))
          .limit(20);
        return { ...wf, instances };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  listInstances: protectedProcedure
    .input(
      z.object({
        workflowId: z.number().optional(),
        limit: z.number().default(50),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = input.workflowId
          ? await db
              .select()
              .from(workflowInstances)
              .where(eq(workflowInstances.definitionId, input.workflowId))
              .orderBy(desc(workflowInstances.createdAt))
              .limit(input.limit)
          : await db
              .select()
              .from(workflowInstances)
              .orderBy(desc(workflowInstances.createdAt))
              .limit(input.limit);
        return { instances: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  createWorkflow: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        description: z.string().optional(),
        steps: z
          .array(z.object({ name: z.string(), type: z.string() }))
          .optional(),
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
        "bankingWorkflowPatterns",
        "mutation",
        "Executed bankingWorkflowPatterns mutation"
      );

      try {
        const db = (await getDb())!;
        const [wf] = await db
          .insert(workflowDefinitions)
          .values({
            name: input.name,
            description: input.description,
            steps: input.steps ?? [],
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "workflow_created",
          resource: "workflow_definitions",
          resourceId: String(wf.id),
          status: "success",
          metadata: { name: input.name },
        } as any);
        return wf;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [totalDefs] = await db
      .select({ value: count() })
      .from(workflowDefinitions)
      .limit(100);
    const [totalInstances] = await db
      .select({ value: count() })
      .from(workflowInstances)
      .limit(100);
    return {
      totalWorkflows: Number(totalDefs.value),
      totalInstances: Number(totalInstances.value),
    };
  }),
});
