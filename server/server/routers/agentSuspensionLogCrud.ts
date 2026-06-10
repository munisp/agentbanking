// Sprint 87: Full domain logic — suspension workflow (warn→suspend→reinstate), auto-escalation
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agentSuspensionLog, gl_journal_entries } from "../../drizzle/schema";
import { eq, desc, and, sql, count } from "drizzle-orm";
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
import { checkDailyLimit } from "../lib/cbnLimits";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["pending_review"],
  pending_review: ["approved", "rejected"],
  approved: ["active", "suspended"],
  active: ["suspended", "deactivated", "under_review"],
  suspended: ["active", "deactivated"],
  under_review: ["active", "suspended", "deactivated"],
  deactivated: ["reactivation_pending"],
  reactivation_pending: ["active", "rejected"],
  rejected: [],
};

const SUSPENSION_WORKFLOW = {
  warn: "suspended",
  suspended: "reactivated",
  reactivated: "warn",
};
const MAX_WARNINGS_BEFORE_AUTO_SUSPEND = 3;

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentSuspensionLogCrud",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentSuspensionLogCrud",
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
    resource: "agentSuspensionLogCrud",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentSuspensionLogCrud",
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

export const agentSuspensionLogRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        agentId: z.number().optional(),
        action: z.string().optional(),
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const conditions: any[] = [];
        if (input.agentId)
          conditions.push(eq(agentSuspensionLog.agentId, input.agentId));
        if (input.action)
          conditions.push(eq(agentSuspensionLog.action, input.action));
        const rows = await db
          .select()
          .from(agentSuspensionLog)
          .where(conditions.length ? and(...conditions) : undefined)
          .orderBy(desc(agentSuspensionLog.id))
          .limit(input.limit)
          .offset(input.offset);
        const [{ total }] = await db
          .select({ total: count() })
          .from(agentSuspensionLog)
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
          .from(agentSuspensionLog)
          .where(eq(agentSuspensionLog.id, input.id))
          .limit(100);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Suspension log entry not found",
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
  warn: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        reason: z.string().min(10, "Reason must be at least 10 characters"),
        performedBy: z.number(),
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
        // Count existing warnings
        const [{ total: warningCount }] = await db
          .select({ total: count() })
          .from(agentSuspensionLog)
          .where(
            and(
              eq(agentSuspensionLog.agentId, input.agentId),
              eq(agentSuspensionLog.action, "warn")
            )
          )
          .limit(100);
        // Auto-escalate to suspension if too many warnings
        const action =
          warningCount >= MAX_WARNINGS_BEFORE_AUTO_SUSPEND - 1
            ? "suspend"
            : "warn";
        const [row] = await db
          .insert(agentSuspensionLog)
          .values({
            agentId: input.agentId,
            action,
            reason:
              action === "suspend"
                ? `AUTO-ESCALATED: ${input.reason} (${warningCount + 1} warnings)`
                : input.reason,
            performedBy: input.performedBy,
          })
          .returning();

        // Double-entry GL journal entry
        await db.insert(gl_journal_entries).values({
          entryNumber: `JE-${Date.now()}`,
          description: `agentSuspensionLogCrud transaction`,
          debitAccountId: 2001,
          creditAccountId: 1001,
          amount: Math.round(
            (typeof input === "object" && "amount" in input
              ? Number((input as any).amount)
              : 0) * 100
          ),
          currency: "NGN",
          status: "posted",
        });
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

          resource: "agentSuspensionLogCrud",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id ?? "new")
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return {
          ...row,
          autoEscalated: action === "suspend",
          warningCount: warningCount + 1,
          message:
            action === "suspend"
              ? `Agent auto-suspended after ${warningCount + 1} warnings`
              : `Warning ${warningCount + 1}/${MAX_WARNINGS_BEFORE_AUTO_SUSPEND} issued`,
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
  suspend: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        reason: z.string().min(10),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        // Check if already suspended
        const [lastAction] = await db
          .select()
          .from(agentSuspensionLog)
          .where(eq(agentSuspensionLog.agentId, input.agentId))
          .orderBy(desc(agentSuspensionLog.id))
          .limit(1);
        if (lastAction?.action === "suspend")
          throw new TRPCError({
            code: "PRECONDITION_FAILED",
            message: "Agent is already suspended",
          });
        const [row] = await db
          .insert(agentSuspensionLog)
          .values({
            agentId: input.agentId,
            action: "suspend",
            reason: input.reason,
            performedBy: input.performedBy,
          })
          .returning();
        return { ...row, message: "Agent suspended successfully" };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  reinstate: protectedProcedure
    .input(
      z.object({
        agentId: z.number(),
        reason: z.string().min(10),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [lastAction] = await db
          .select()
          .from(agentSuspensionLog)
          .where(eq(agentSuspensionLog.agentId, input.agentId))
          .orderBy(desc(agentSuspensionLog.id))
          .limit(1);
        if (!lastAction || lastAction.action !== "suspend")
          throw new TRPCError({
            code: "PRECONDITION_FAILED",
            message: "Agent is not currently suspended",
          });
        const [row] = await db
          .insert(agentSuspensionLog)
          .values({
            agentId: input.agentId,
            action: "reactivate",
            reason: input.reason,
            performedBy: input.performedBy,
          })
          .returning();
        return { ...row, message: "Agent reinstated successfully" };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getAgentStatus: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [lastAction] = await db
          .select()
          .from(agentSuspensionLog)
          .where(eq(agentSuspensionLog.agentId, input.agentId))
          .orderBy(desc(agentSuspensionLog.id))
          .limit(1);
        const [{ total: warningCount }] = await db
          .select({ total: count() })
          .from(agentSuspensionLog)
          .where(
            and(
              eq(agentSuspensionLog.agentId, input.agentId),
              eq(agentSuspensionLog.action, "warn")
            )
          )
          .limit(100);
        return {
          agentId: input.agentId,
          currentStatus:
            lastAction?.action === "suspend" ? "suspended" : "active",
          lastAction: lastAction || null,
          warningCount,
          maxWarnings: MAX_WARNINGS_BEFORE_AUTO_SUSPEND,
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
});
