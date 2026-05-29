import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
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
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

export const stablecoinRailsRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "stable_wallets"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [supplyRes, volumeRes, devRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'balance')::numeric), 0) as supply FROM "stable_wallets" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ supply: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'amount')::numeric), 0) as vol FROM "stable_wallets" WHERE created_at >= CURRENT_DATE`
          )
          .catch(() => ({ rows: [{ vol: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(AVG((data->>'peg_deviation')::numeric), 0) as dev FROM "stable_wallets" WHERE data->>'peg_deviation' IS NOT NULL`
          )
          .catch(() => ({ rows: [{ dev: 0 }] })),
      ]);
      const supplyResult = (supplyRes as any).rows?.[0]?.supply;
      const volumeResult = (volumeRes as any).rows?.[0]?.vol;
      const devResult = (devRes as any).rows?.[0]?.dev;
      return {
        totalWallets: total,
        circulatingSupply: Number(supplyResult ?? 0),
        dailyVolume: Number(volumeResult ?? 0),
        pegDeviation:
          Number(devResult ?? 0) !== 0
            ? Number(devResult).toFixed(4) + "%"
            : "0.00%",
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalWallets: 0,
        circulatingSupply: 0,
        dailyVolume: 0,
        pegDeviation: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "stable_wallets" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "stable_wallets"`
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
        !input.data.walletAddress ||
        typeof input.data.walletAddress !== "string"
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "walletAddress is required",
        });
      }
      const amount = Number(input.data.amount);
      if (amount !== undefined && amount < 0) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "amount cannot be negative",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "stable_wallets" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "stable_wallets" WHERE id = ${recordId}`
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
        "active",
        "frozen",
        "suspended",
        "closed",
        "confirmed",
        "pending",
        "failed",
        "processing",
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
        sql`UPDATE "stable_wallets" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "stable_wallets" GROUP BY status`
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
      { name: "Stablecoin Rails (Go)", url: "http://localhost:8263/health" },
      { name: "Stablecoin Rails (Rust)", url: "http://localhost:8264/health" },
      {
        name: "Stablecoin Rails (Python)",
        url: "http://localhost:8265/health",
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
