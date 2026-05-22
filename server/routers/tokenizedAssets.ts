import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

export const tokenizedAssetsRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "tokenized_assets"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [holdersRes, marketCapRes, dividendsRes] = await Promise.all([
        db.execute(sql`SELECT COALESCE(SUM((data->>'holder_count')::numeric), 0) as cnt FROM "tokenized_assets" WHERE status = 'active'`).catch(() => ({rows:[{cnt:0}]})),
        db.execute(sql`SELECT COALESCE(SUM((data->>'total_tokens')::numeric * (data->>'price_per_token')::numeric), 0) as cap FROM "tokenized_assets" WHERE status = 'active'`).catch(() => ({rows:[{cap:0}]})),
        db.execute(sql`SELECT COALESCE(SUM((data->>'dividends_paid')::numeric), 0) as total FROM "tokenized_assets"`).catch(() => ({rows:[{total:0}]})),
      ]);
      const holdersResult = (holdersRes as any).rows?.[0]?.cnt;
      const marketCapResult = (marketCapRes as any).rows?.[0]?.cap;
      const dividendsResult = (dividendsRes as any).rows?.[0]?.total;
      return {
      totalAssets: total,
      totalHolders: Number(holdersResult ?? 0),
      marketCap: Number(marketCapResult ?? 0),
      dividendsPaid: Number(dividendsResult ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalAssets: 0,
        totalHolders: 0,
        marketCap: 0,
        dividendsPaid: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "tokenized_assets" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "tokenized_assets"`
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

      if (!input.data.assetName || typeof input.data.assetName !== 'string') {
        throw new TRPCError({ code: "BAD_REQUEST", message: "assetName is required" });
      }
      if (!input.data.assetType || !["real_estate", "commodity", "equipment", "vehicle", "agricultural_land"].includes(input.data.assetType as string)) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "assetType must be one of: real_estate, commodity, equipment, vehicle, agricultural_land" });
      }
      const totalTokens = Number(input.data.totalTokens);
      if (!totalTokens || totalTokens < 10) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "totalTokens must be at least 10" });
      }
      const pricePerToken = Number(input.data.pricePerToken);
      if (!pricePerToken || pricePerToken < 100) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "pricePerToken must be at least ₦100" });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "tokenized_assets" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "tokenized_assets" WHERE id = ${recordId}`
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

      const validStatuses = ["active", "sold_out", "suspended", "pending"];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "Status must be one of: " + validStatuses.join(", ") });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "tokenized_assets" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "tokenized_assets" GROUP BY status`
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
      { name: "Tokenized Assets (Go)", url: "http://localhost:8284/health" },
      { name: "Tokenized Assets (Rust)", url: "http://localhost:8285/health" },
      {
        name: "Tokenized Assets (Python)",
        url: "http://localhost:8286/health",
      },
    ];
    const results = await Promise.all(
      services.map(async (svc) => {
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
