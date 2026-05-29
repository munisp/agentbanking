import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { validateAmount, validateStatusTransition, auditFinancialAction } from "../lib/transactionHelper";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  "pending": ["active", "completed", "cancelled", "rejected"],
  "active": ["completed", "suspended", "cancelled"],
  "completed": ["archived"],
  "suspended": ["active", "cancelled"],
  "cancelled": [],
  "rejected": [],
  "archived": []
};

export const satelliteConnectivityRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "satellite_links"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [activeRes, failoverRes, syncRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "satellite_links" WHERE status = 'connected'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "satellite_links" WHERE status = 'failover' AND created_at >= CURRENT_DATE`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'data_synced_mb')::numeric), 0) as mb FROM "satellite_links"`
          )
          .catch(() => ({ rows: [{ mb: 0 }] })),
      ]);
      const activeResult = (activeRes as any).rows?.[0]?.cnt;
      const failoverResult = (failoverRes as any).rows?.[0]?.cnt;
      const syncResult = (syncRes as any).rows?.[0]?.mb;
      return {
        activeLinks: Number(activeResult ?? 0),
        failoversToday: Number(failoverResult ?? 0),
        dataSynced: Number(Number(syncResult ?? 0).toFixed(2)),
        coveragePercent:
          total > 0
            ? ((Number(activeResult ?? 0) / total) * 100).toFixed(1) + "%"
            : "0%",
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        activeLinks: 0,
        failoversToday: 0,
        dataSynced: 0,
        coveragePercent: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "satellite_links" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "satellite_links"`
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

      if (!input.data.agentCode || typeof input.data.agentCode !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "agentCode is required",
        });
      }
      if (
        !input.data.provider ||
        !["starlink", "ast_spacemobile", "oneweb", "vsat"].includes(
          input.data.provider as string
        )
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message:
            "provider must be one of: starlink, ast_spacemobile, oneweb, vsat",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "satellite_links" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "satellite_links" WHERE id = ${recordId}`
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

      const validStatuses = [
        "connected",
        "disconnected",
        "failover",
        "syncing",
      ];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Status must be one of: " + validStatuses.join(", "),
        });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "satellite_links" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "satellite_links" GROUP BY status`
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
        name: "Satellite Connectivity (Go)",
        url: "http://localhost:8272/health",
      },
      {
        name: "Satellite Connectivity (Rust)",
        url: "http://localhost:8273/health",
      },
      {
        name: "Satellite Connectivity (Python)",
        url: "http://localhost:8274/health",
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
