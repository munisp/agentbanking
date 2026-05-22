import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

export const carbonCreditMarketplaceRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "carbon_projects"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [issuedRes, retiredRes, volumeRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'credits_issued')::numeric), 0) as total FROM "carbon_projects" WHERE status = 'verified'`
          )
          .catch(() => ({ rows: [{ total: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'credits_retired')::numeric), 0) as total FROM "carbon_projects"`
          )
          .catch(() => ({ rows: [{ total: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'trade_volume')::numeric), 0) as total FROM "carbon_projects"`
          )
          .catch(() => ({ rows: [{ total: 0 }] })),
      ]);
      const issuedResult = (issuedRes as any).rows?.[0]?.total;
      const retiredResult = (retiredRes as any).rows?.[0]?.total;
      const volumeResult = (volumeRes as any).rows?.[0]?.total;
      return {
        totalProjects: total,
        creditsIssued: Number(issuedResult ?? 0),
        creditsRetired: Number(retiredResult ?? 0),
        marketVolume: Number(volumeResult ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalProjects: 0,
        creditsIssued: 0,
        creditsRetired: 0,
        marketVolume: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "carbon_projects" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "carbon_projects"`
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

      if (
        !input.data.projectName ||
        typeof input.data.projectName !== "string"
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "projectName is required",
        });
      }
      if (
        !input.data.projectType ||
        ![
          "reforestation",
          "solar",
          "wind",
          "cookstove",
          "biogas",
          "waste_mgmt",
        ].includes(input.data.projectType as string)
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message:
            "projectType must be one of: reforestation, solar, wind, cookstove, biogas, waste_mgmt",
        });
      }
      const credits = Number(input.data.creditsRequested);
      if (!credits || credits < 1) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "creditsRequested must be at least 1 tonne CO2e",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "carbon_projects" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "carbon_projects" WHERE id = ${recordId}`
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
        "verified",
        "pending",
        "rejected",
        "expired",
        "active",
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
        sql`UPDATE "carbon_projects" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "carbon_projects" GROUP BY status`
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
        name: "Carbon Credit Marketplace (Go)",
        url: "http://localhost:8281/health",
      },
      {
        name: "Carbon Credit Marketplace (Rust)",
        url: "http://localhost:8282/health",
      },
      {
        name: "Carbon Credit Marketplace (Python)",
        url: "http://localhost:8283/health",
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
