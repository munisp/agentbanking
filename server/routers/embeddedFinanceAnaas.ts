import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

export const embeddedFinanceAnaasRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "anaas_tenants"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [agentsRes, revenueRes, slaRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'agent_count')::numeric), 0) as cnt FROM "anaas_tenants" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'monthly_volume')::numeric), 0) as revenue FROM "anaas_tenants" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ revenue: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(AVG((data->>'sla_score')::numeric), 0) as avg_sla FROM "anaas_tenants" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ avg_sla: 0 }] })),
      ]);
      const agentsResult = (agentsRes as any).rows?.[0]?.cnt;
      const revenueResult = (revenueRes as any).rows?.[0]?.revenue;
      const slaResult = (slaRes as any).rows?.[0]?.avg_sla;
      return {
        totalTenants: total,
        sharedAgents: Number(agentsResult ?? 0),
        monthlyRevenue: Number(revenueResult ?? 0),
        avgSlaScore: total > 0 ? Number(Number(slaResult ?? 0).toFixed(1)) : 0,
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalTenants: 0,
        sharedAgents: 0,
        monthlyRevenue: 0,
        avgSlaScore: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
  }),

  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
        search: z.string().optional(),
        status: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      const db = (await getDb())!;
      try {
        const lim = input.limit;
        const off = input.offset;
        const result = await db.execute(
          sql`SELECT id, data, status, created_at, agent_id FROM "anaas_tenants" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "anaas_tenants"`
        );
        return {
          items: ((result as any).rows ?? []).map((row: any) => ({
            id: row.id,
            ...((typeof row.data === "string"
              ? JSON.parse(row.data)
              : row.data) || {}),
            status: row.status,
            createdAt: row.created_at,
            agentId: row.agent_id,
          })),
          total: Number((countResult as any).rows?.[0]?.cnt ?? 0),
        };
      } catch {
        return { items: [] as any[], total: 0 };
      }
    }),

  create: protectedProcedure
    .input(z.object({ data: z.record(z.string(), z.unknown()) }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;

      if (!input.data.tenantName || typeof input.data.tenantName !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "tenantName is required",
        });
      }
      if (
        !input.data.type ||
        !["bank", "fintech", "telco", "insurance"].includes(
          input.data.type as string
        )
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "type must be one of: bank, fintech, telco, insurance",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "anaas_tenants" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
      );
      const id = (result as any).rows?.[0]?.id;
      return { id, status: "created" };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const db = (await getDb())!;
      const recordId = input.id;
      const result = await db.execute(
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "anaas_tenants" WHERE id = ${recordId}`
      );
      if (!(result as any).rows?.length) {
        throw new TRPCError({ code: "NOT_FOUND", message: "Record not found" });
      }
      const row: any = (result as any).rows[0];
      return {
        id: row.id,
        ...((typeof row.data === "string" ? JSON.parse(row.data) : row.data) ||
          {}),
        status: row.status,
        createdAt: row.created_at,
        agentId: row.agent_id,
        metadata: row.metadata,
      };
    }),

  updateStatus: protectedProcedure
    .input(z.object({ id: z.number(), status: z.string() }))
    .mutation(async ({ input }) => {
      const db = (await getDb())!;

      const validStatuses = ["active", "trial", "suspended", "churned"];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Status must be one of: " + validStatuses.join(", "),
        });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "anaas_tenants" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "anaas_tenants" GROUP BY status`
      );
      const byStatus = Object.fromEntries(
        ((result as any).rows ?? []).map((r: any) => [r.status, Number(r.cnt)])
      );
      return {
        byStatus,
        total: Object.values(byStatus).reduce(
          (a: number, b: any) => a + Number(b),
          0
        ),
        generatedAt: new Date().toISOString(),
      };
    } catch {
      return {
        byStatus: {} as Record<string, number>,
        total: 0,
        generatedAt: new Date().toISOString(),
      };
    }
  }),

  serviceHealth: protectedProcedure.query(async () => {
    const services = [
      {
        name: "Embedded Finance / ANaaS (Go)",
        url: "http://localhost:8248/health",
      },
      {
        name: "Embedded Finance / ANaaS (Rust)",
        url: "http://localhost:8249/health",
      },
      {
        name: "Embedded Finance / ANaaS (Python)",
        url: "http://localhost:8250/health",
      },
    ];
    const results = await Promise.all(
      services.map(async svc => {
        try {
          const res = await fetch(svc.url, {
            signal: AbortSignal.timeout(3000),
          });
          const data = await res.json();
          return { ...svc, status: "healthy" as const, data };
        } catch {
          return { ...svc, status: "unhealthy" as const, data: null };
        }
      })
    );
    return { services: results, checkedAt: new Date().toISOString() };
  }),
});
