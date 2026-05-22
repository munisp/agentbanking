import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

export const nfcTapToPayRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "nfc_terminals"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [activeRes, todayRes, volumeRes, avgTimeRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "nfc_terminals" WHERE status = 'active'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "nfc_terminals" WHERE created_at >= CURRENT_DATE`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'amount')::numeric), 0) as vol FROM "nfc_terminals" WHERE created_at >= CURRENT_DATE`
          )
          .catch(() => ({ rows: [{ vol: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(AVG((data->>'tap_duration_ms')::numeric), 0) as avg_ms FROM "nfc_terminals" WHERE status = 'approved'`
          )
          .catch(() => ({ rows: [{ avg_ms: 0 }] })),
      ]);
      const activeResult = (activeRes as any).rows?.[0]?.cnt;
      const todayResult = (todayRes as any).rows?.[0]?.cnt;
      const volumeResult = (volumeRes as any).rows?.[0]?.vol;
      const avgTimeResult = (avgTimeRes as any).rows?.[0]?.avg_ms;
      return {
        activeTerminals: Number(activeResult ?? 0),
        transactionsToday: Number(todayResult ?? 0),
        volumeToday: Number(volumeResult ?? 0),
        avgTapTime:
          total > 0
            ? (Number(avgTimeResult ?? 0) / 1000).toFixed(2) + "s"
            : "0s",
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        activeTerminals: 0,
        transactionsToday: 0,
        volumeToday: 0,
        avgTapTime: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "nfc_terminals" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "nfc_terminals"`
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

      if (!input.data.terminalId || typeof input.data.terminalId !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "terminalId is required for NFC registration",
        });
      }
      if (
        !input.data.deviceModel ||
        typeof input.data.deviceModel !== "string"
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "deviceModel is required (Android NFC-enabled device)",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "nfc_terminals" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "nfc_terminals" WHERE id = ${recordId}`
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
        "approved",
        "declined",
        "pending",
        "reversed",
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
        sql`UPDATE "nfc_terminals" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "nfc_terminals" GROUP BY status`
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
      { name: "NFC Tap-to-Pay (Go)", url: "http://localhost:8236/health" },
      { name: "NFC Tap-to-Pay (Rust)", url: "http://localhost:8237/health" },
      {
        name: "NFC Tap-to-Pay (Python)",
        url: "http://localhost:8238/health",
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
