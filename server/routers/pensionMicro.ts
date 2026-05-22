import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

export const pensionMicroRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "pension_accounts"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [contribRes, withdrawRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'total_contributed')::numeric), 0) as total FROM "pension_accounts"`
          )
          .catch(() => ({ rows: [{ total: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "pension_accounts" WHERE status = 'withdrawn'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
      ]);
      const contribResult = (contribRes as any).rows?.[0]?.total;
      const withdrawResult = (withdrawRes as any).rows?.[0]?.cnt;
      return {
        totalAccounts: total,
        totalContributions: Number(contribResult ?? 0),
        avgMonthlyContrib:
          total > 0
            ? Number(
                (Number(contribResult ?? 0) / Math.max(total, 1)).toFixed(2)
              )
            : 0,
        withdrawalRequests: Number(withdrawResult ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalAccounts: 0,
        totalContributions: 0,
        avgMonthlyContrib: 0,
        withdrawalRequests: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "pension_accounts" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "pension_accounts"`
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

      if (!input.data.holderName || typeof input.data.holderName !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "holderName is required for pension account",
        });
      }
      const monthlyContrib = Number(input.data.monthlyContribution);
      if (!monthlyContrib || monthlyContrib < 100 || monthlyContrib > 1000000) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "monthlyContribution must be between ₦100 and ₦1,000,000",
        });
      }
      if (!input.data.rsaPin || typeof input.data.rsaPin !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message:
            "rsaPin (Retirement Savings Account PIN) is required for PenCom compliance",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "pension_accounts" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "pension_accounts" WHERE id = ${recordId}`
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

      const validStatuses = ["active", "dormant", "matured", "withdrawn"];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Status must be one of: " + validStatuses.join(", "),
        });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "pension_accounts" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "pension_accounts" GROUP BY status`
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
        name: "Pension Micro-Contributions (Go)",
        url: "http://localhost:8278/health",
      },
      {
        name: "Pension Micro-Contributions (Rust)",
        url: "http://localhost:8279/health",
      },
      {
        name: "Pension Micro-Contributions (Python)",
        url: "http://localhost:8280/health",
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
