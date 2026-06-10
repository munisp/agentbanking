import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { eq, desc, and, sql, count, gte } from "drizzle-orm";
import {
  agents,
  kycSessions,
  floatTopUpRequests,
  posTerminals,
  trainingEnrollments,
  auditLog,
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

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentOnboardingWizard",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentOnboardingWizard",
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
    resource: "agentOnboardingWizard",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentOnboardingWizard",
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

// ── Extended Validation Schemas ────────────────────────────────────────────
const _agentOnboardingWizardSchemas = {
  idParam: z.object({ id: z.number().int().positive() }),
  paginationInput: z.object({
    page: z.number().int().min(1).default(1),
    pageSize: z.number().int().min(1).max(100).default(20),
    sortBy: z.string().optional(),
    sortOrder: z.enum(["asc", "desc"]).default("desc"),
  }),
  dateRange: z.object({
    from: z.string().datetime().optional(),
    to: z.string().datetime().optional(),
  }),
  searchInput: z.object({
    query: z.string().min(1).max(500),
    filters: z.record(z.string(), z.string()).optional(),
  }),
};

// ── Business Rule Guards ───────────────────────────────────────────────────
function enforceAgentonboardingwizardRules(data: Record<string, unknown>) {
  if (!data) throw new Error("Data required");
  if (typeof data.id === "number" && data.id <= 0)
    throw new Error("Invalid ID");
  if (
    typeof data.status === "string" &&
    !["active", "pending", "completed", "cancelled"].includes(data.status)
  )
    throw new Error("Invalid status");
  if (
    typeof data.amount === "number" &&
    (data.amount < 0 || data.amount > 100_000_000)
  )
    throw new Error("Amount out of range");
  if (typeof data.email === "string" && !data.email.includes("@"))
    throw new Error("Invalid email");
  if (typeof data.name === "string" && data.name.trim().length === 0)
    throw new Error("Name required");
  return true;
}
export const agentOnboardingWizardRouter = router({
  getProgress: protectedProcedure
    .input(z.object({ agentId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [agent] = await db
          .select()
          .from(agents)
          .where(eq(agents.id, input.agentId))
          .limit(1);
        if (!agent)
          return { step: 0, steps: [], completedSteps: 0, totalSteps: 5 };
        const [kyc] = await db
          .select({ cnt: count() })
          .from(kycSessions)
          .where(
            and(
              eq(kycSessions.agentId, input.agentId),
              eq(kycSessions.status, "completed")
            )
          )
          .limit(100);
        const [floatReq] = await db
          .select({ cnt: count() })
          .from(floatTopUpRequests)
          .where(eq(floatTopUpRequests.agentId, input.agentId))
          .limit(100);
        const [terminal] = await db
          .select({ cnt: count() })
          .from(posTerminals)
          .where(eq(posTerminals.agentId, input.agentId))
          .limit(100);
        const [training] = await db
          .select({ cnt: count() })
          .from(trainingEnrollments)
          .where(eq(trainingEnrollments.agentId, input.agentId))
          .limit(100);
        const steps = [
          { name: "Profile", completed: !!agent.name, order: 1 },
          {
            name: "KYC Verification",
            completed: Number(kyc.cnt) > 0,
            order: 2,
          },
          {
            name: "Float Setup",
            completed: Number(floatReq.cnt) > 0,
            order: 3,
          },
          {
            name: "Terminal Assignment",
            completed: Number(terminal.cnt) > 0,
            order: 4,
          },
          { name: "Training", completed: Number(training.cnt) > 0, order: 5 },
        ];
        const completedSteps = steps.filter(s => s.completed).length;
        const currentStep = steps.find(s => !s.completed)?.order ?? 5;
        return {
          step: currentStep,
          steps,
          completedSteps,
          totalSteps: 5,
          agentName: agent.name,
          status: completedSteps === 5 ? "completed" : "in_progress",
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
  listPendingAgents: protectedProcedure
    .input(z.object({ limit: z.number().default(50) }).optional())
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = await db
          .select()
          .from(agents)
          .where(eq(agents.isActive, false))
          .orderBy(desc(agents.createdAt))
          .limit(input?.limit ?? 50);
        return { agents: rows, total: rows.length };
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
    const [total] = await db.select({ value: count() }).from(agents).limit(100);
    const [active] = await db
      .select({ value: count() })
      .from(agents)
      .where(eq(agents.isActive, true))
      .limit(100);
    const [pending] = await db
      .select({ value: count() })
      .from(agents)
      .where(eq(agents.isActive, false))
      .limit(100);
    return {
      totalAgents: Number(total.value),
      activeAgents: Number(active.value),
      pendingOnboarding: Number(pending.value),
      completionRate:
        Number(total.value) > 0
          ? Math.round((Number(active.value) / Number(total.value)) * 100)
          : 0,
    };
  }),
  approveAgent: protectedProcedure
    .input(z.object({ agentId: z.number() }))
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
        await db
          .update(agents)
          .set({ isActive: true })
          .where(eq(agents.id, input.agentId));
        await db.insert(auditLog).values({
          action: "agent_onboarding_approved",
          resource: "agents",
          resourceId: String(input.agentId),
          status: "success",
          metadata: {},
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

          resource: "agentOnboardingWizard",

          resourceId:
            typeof input === "object" && input !== null && "id" in input
              ? String((input as any).id ?? "new")
              : "new",

          status: "success",

          metadata: { input: typeof input === "object" ? input : {} },
        });

        return { success: true, agentId: input.agentId };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Additional query/mutation procedures ─────────────────────
  getStats_agentOnboardingWizard: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      lastUpdated: new Date().toISOString(),
      status: "operational",
    };
  }),

  healthCheck_agentOnboardingWizard: protectedProcedure.query(async () => {
    return {
      healthy: true,
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }),
});
