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

export const iotSmartPosRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "iot_devices"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [onlineRes, alertRes, predictRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "iot_devices" WHERE status = 'online'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "iot_devices" WHERE (data->>'alert_active')::boolean = true`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "iot_devices" WHERE (data->>'predicted_failure')::boolean = true`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
      ]);
      const onlineResult = (onlineRes as any).rows?.[0]?.cnt;
      const alertResult = (alertRes as any).rows?.[0]?.cnt;
      const predictResult = (predictRes as any).rows?.[0]?.cnt;
      return {
        totalDevices: total,
        onlineDevices: Number(onlineResult ?? 0),
        activeAlerts: Number(alertResult ?? 0),
        predictedFailures: Number(predictResult ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalDevices: 0,
        onlineDevices: 0,
        activeAlerts: 0,
        predictedFailures: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "iot_devices" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "iot_devices"`
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

      if (!input.data.deviceType || typeof input.data.deviceType !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message:
            "deviceType is required (e.g., temperature, gps, tamper, battery)",
        });
      }
      if (!input.data.location || typeof input.data.location !== "string") {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "location is required for IoT device registration",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "iot_devices" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "iot_devices" WHERE id = ${recordId}`
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

      const validStatuses = ["online", "offline", "maintenance", "tampered"];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Status must be one of: " + validStatuses.join(", "),
        });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "iot_devices" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "iot_devices" GROUP BY status`
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
      { name: "IoT Smart POS (Go)", url: "http://localhost:8266/health" },
      { name: "IoT Smart POS (Rust)", url: "http://localhost:8267/health" },
      {
        name: "IoT Smart POS (Python)",
        url: "http://localhost:8268/health",
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
