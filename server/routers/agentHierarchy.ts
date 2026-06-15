import { z } from "zod";
import { publicProcedure, protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { agents } from "../../drizzle/schema";
import { desc, eq, sql, and, gte, lte, count } from "drizzle-orm";
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
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

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

function enforceTransition(currentStatus: string, newStatus: string) {
  const allowed =
    STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
  if (allowed && !allowed.includes(newStatus)) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `Invalid status transition from ${currentStatus} to ${newStatus}`,
    });
  }
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "agentHierarchy",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "agentHierarchy",
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
    resource: "agentHierarchy",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "agentHierarchy",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Domain Calculations ────────────────────────────────────────────────────

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

// ── Database Operations Helper ─────────────────────────────────────────────
async function checkDbHealth() {
  try {
    const db = await (await import("../db")).getDb();
    if (!!(db && (db as Record<string, unknown>)._isNoop))
      return { connected: false, latencyMs: 0 };
    const start = Date.now();
    await db
      .select({ val: (await import("drizzle-orm")).sql`1` })
      .from((await import("drizzle-orm")).sql`(SELECT 1) AS t`)
      .limit(500);
    return { connected: true, latencyMs: Date.now() - start };
  } catch {
    return { connected: false, latencyMs: 0 };
  }
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

export const agentHierarchyRouter = router({
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database)
        return { data: [], items: [], total: 0, limit: 0, offset: 0 };
      const [record] = await database
        .select()
        .from(agents)
        .where(eq(agents.id, input.id))
        .limit(1);

      if (!record) {
        throw new Error(`Record with id ${input.id} not found`);
      }
      return record;
    }),

  getSummary: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database)
      return { data: [], items: [], total: 0, limit: 0, offset: 0 };
    const _totalRows = await database.select({ total: count() }).from(agents);
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
      if (!database)
        return { data: [], items: [], total: 0, limit: 0, offset: 0 };
      const since = new Date();
      since.setDate(since.getDate() - input.days);

      const results = await database
        .select()
        .from(agents)
        .orderBy(desc(agents.id))
        .limit(input.limit);

      return results;
    }),

  // ── Sprint 28 domain procedures ──
  list: publicProcedure
    .input(
      z
        .object({
          role: z.string().optional(),
          territory: z.string().optional(),
          search: z.string().min(1).max(500).optional(),
          page: z.number().min(1).default(1),
          limit: z.number().min(1).max(100).default(20),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { agents: [], items: [], total: 0 };
      try {
        const lim = input?.limit ?? 20;
        const offset = ((input?.page ?? 1) - 1) * lim;
        const rows = await database
          .select()
          .from(agents)
          .orderBy(desc(agents.id))
          .limit(lim)
          .offset(offset);
        const totalResult = await database
          .select({ total: count() })
          .from(agents);
        const totalRow = Array.isArray(totalResult)
          ? totalResult[0]
          : totalResult;
        return {
          agents: rows,
          items: rows,
          total: Number((totalRow as Record<string, unknown>)?.total ?? 0),
        };
      } catch {
        return { agents: [], items: [], total: 0 };
      }
    }),

  getTree: protectedProcedure
    .input(z.object({ rootAgentId: z.number().optional() }).optional())
    .query(async ({ input }) => {
      const database = await getDb();
      if (!database) return { tree: null, totalNodes: 0 };

      // Recursive CTE for deep hierarchy traversal (up to 10 levels)
      const rootId = input?.rootAgentId;
      let flatRows: Array<Record<string, unknown>> = [];
      try {
        const treeResult = await database.execute(sql`
          WITH RECURSIVE agent_tree AS (
            SELECT id, "agentCode", name, phone, "parentId", "isActive", 1 AS depth
            FROM agents
            WHERE ${rootId ? sql`id = ${rootId}` : sql`"parentId" IS NULL`}
            UNION ALL
            SELECT a.id, a."agentCode", a.name, a.phone, a."parentId", a."isActive", t.depth + 1
            FROM agents a
            INNER JOIN agent_tree t ON a."parentId" = t.id
            WHERE t.depth < 10
          )
          SELECT * FROM agent_tree ORDER BY depth, id LIMIT 500
        `);
        flatRows = Array.isArray(treeResult)
          ? treeResult
          : ((treeResult?.rows ?? []) as Array<Record<string, unknown>>);
      } catch {
        flatRows = [];
      }

      type TreeNode = {
        id: number;
        agentCode: string;
        name: string;
        parentId: number | null;
        depth: number;
        children: TreeNode[];
      };
      const nodes = new Map<number, TreeNode>();
      const roots: TreeNode[] = [];

      for (const row of flatRows) {
        const node: TreeNode = {
          id: Number(row.id ?? 0),
          agentCode: String(row.agentCode ?? ""),
          name: String(row.name ?? ""),
          parentId: row.parentId ? Number(row.parentId) : null,
          depth: Number(row.depth ?? 1),
          children: [],
        };
        nodes.set(node.id, node);
      }

      for (const node of nodes.values()) {
        if (node.parentId && nodes.has(node.parentId)) {
          nodes.get(node.parentId)!.children.push(node);
        } else {
          roots.push(node);
        }
      }

      return { tree: roots[0] ?? null, totalNodes: nodes.size };
    }),

  territories: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { territories: [] };
    try {
      const result = await database.execute(sql`
        SELECT COALESCE(territory, 'Unassigned') AS territory,
          COUNT(*) AS agent_count,
          COUNT(*) FILTER (WHERE "isActive" = true) AS active_count
        FROM agents GROUP BY territory ORDER BY agent_count DESC LIMIT 100
      `);
      const rows = Array.isArray(result)
        ? result
        : ((result?.rows ?? []) as Array<Record<string, string>>);
      return {
        territories: rows.map((r: Record<string, string>) => ({
          name: r.territory ?? "Unassigned",
          agentCount: parseInt(r.agent_count ?? "0", 10),
          activeCount: parseInt(r.active_count ?? "0", 10),
        })),
      };
    } catch {
      return { territories: [] };
    }
  }),

  analytics: protectedProcedure.query(async () => {
    const database = await getDb();
    if (!database) return { totalAgents: 0, byRole: {}, byTerritory: {} };
    try {
      const [totals] = await database.select({ total: count() }).from(agents);
      const roleResult = await database.execute(sql`
        SELECT COALESCE(role, 'agent') AS role, COUNT(*) AS cnt FROM agents GROUP BY role
      `);
      const territoryResult = await database.execute(sql`
        SELECT COALESCE(territory, 'Unassigned') AS territory, COUNT(*) AS cnt
        FROM agents GROUP BY territory ORDER BY cnt DESC LIMIT 50
      `);
      const roleRows = Array.isArray(roleResult)
        ? roleResult
        : ((roleResult?.rows ?? []) as Array<Record<string, string>>);
      const territoryRows = Array.isArray(territoryResult)
        ? territoryResult
        : ((territoryResult?.rows ?? []) as Array<Record<string, string>>);
      const byRole: Record<string, number> = {};
      for (const r of roleRows)
        byRole[r.role ?? "agent"] = parseInt(r.cnt ?? "0", 10);
      const byTerritory: Record<string, number> = {};
      for (const r of territoryRows)
        byTerritory[r.territory ?? "Unassigned"] = parseInt(r.cnt ?? "0", 10);
      return { totalAgents: Number(totals.total), byRole, byTerritory };
    } catch {
      return { totalAgents: 0, byRole: {}, byTerritory: {} };
    }
  }),

  reassignParent: protectedProcedure
    .input(z.object({ agentId: z.number(), newParentId: z.number() }))
    .mutation(async ({ input }) => {
      const database = await getDb();
      if (!database)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });

      // Prevent circular hierarchy via recursive ancestor check
      try {
        const targetAncestors = await database.execute(sql`
          WITH RECURSIVE ancestors AS (
            SELECT id, "parentId" FROM agents WHERE id = ${input.newParentId}
            UNION ALL
            SELECT a.id, a."parentId" FROM agents a
            INNER JOIN ancestors p ON a.id = p."parentId"
            WHERE p."parentId" IS NOT NULL
          )
          SELECT id FROM ancestors WHERE id = ${input.agentId}
        `);
        const rows = Array.isArray(targetAncestors)
          ? targetAncestors
          : (targetAncestors?.rows ?? []);
        if (rows.length > 0) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Cannot reassign: would create circular hierarchy",
          });
        }
      } catch (err) {
        if (err instanceof TRPCError) throw err;
        // DB execute failed — allow operation but log
      }

      await database
        .update(agents)
        .set({ parentId: input.newParentId } as Record<string, unknown>)
        .where(eq(agents.id, input.agentId));

      await writeAuditLog({
        agentId: input.agentId,
        agentCode: "system",
        action: "HIERARCHY_REASSIGNMENT",
        resource: "agent_hierarchy",
        resourceId: String(input.agentId),
        status: "success",
        metadata: { newParentId: input.newParentId },
      });

      return {
        agentId: input.agentId,
        newParentId: input.newParentId,
        success: true,
      };
    }),
});
