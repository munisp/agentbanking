import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["submitted", "cancelled"],
  submitted: ["under_review", "rejected"],
  under_review: ["approved", "rejected"],
  approved: ["disbursed"],
  disbursed: ["repaying"],
  repaying: ["completed", "defaulted"],
  completed: [],
  defaulted: ["repaying"],
  rejected: [],
  cancelled: [],
};

export const payrollDisbursementRouter = router({
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    let total = 0;
    try {
      const result = await db.execute(
        sql`SELECT COUNT(*) as cnt FROM "payroll_employers"`
      );
      total = Number((result as any).rows?.[0]?.cnt ?? 0);

      const [empRes, disbursedRes, pendingRes] = await Promise.all([
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'employee_count')::numeric), 0) as cnt FROM "payroll_employers" WHERE status = 'processed'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
        db
          .execute(
            sql`SELECT COALESCE(SUM((data->>'total_amount')::numeric), 0) as total FROM "payroll_employers" WHERE status = 'processed' AND created_at >= date_trunc('month', CURRENT_DATE)`
          )
          .catch(() => ({ rows: [{ total: 0 }] })),
        db
          .execute(
            sql`SELECT COUNT(*) as cnt FROM "payroll_employers" WHERE status = 'pending'`
          )
          .catch(() => ({ rows: [{ cnt: 0 }] })),
      ]);
      const empResult = (empRes as any).rows?.[0]?.cnt;
      const disbursedResult = (disbursedRes as any).rows?.[0]?.total;
      const pendingResult = (pendingRes as any).rows?.[0]?.cnt;
      return {
        totalEmployers: total,
        totalEmployees: Number(empResult ?? 0),
        monthlyDisbursed: Number(disbursedResult ?? 0),
        pendingCashOut: Number(pendingResult ?? 0),
        lastUpdated: new Date().toISOString(),
      };
    } catch {
      return {
        totalEmployers: 0,
        totalEmployees: 0,
        monthlyDisbursed: 0,
        pendingCashOut: 0,
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
          sql`SELECT id, data, status, created_at, agent_id FROM "payroll_employers" ORDER BY created_at DESC LIMIT ${lim} OFFSET ${off}`
        );
        const countResult = await db.execute(
          sql`SELECT COUNT(*) as cnt FROM "payroll_employers"`
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
        !input.data.employerName ||
        typeof input.data.employerName !== "string"
      ) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "employerName is required",
        });
      }
      const empCount = Number(input.data.employeeCount);
      if (!empCount || empCount < 1 || empCount > 100000) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "employeeCount must be between 1 and 100,000",
        });
      }
      const totalAmount = Number(input.data.totalAmount);
      if (!totalAmount || totalAmount < 30000) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "totalAmount must be at least ₦30,000 (minimum wage)",
        });
      }
      const jsonStr = JSON.stringify(input.data);
      const result = await db.execute(
        sql`INSERT INTO "payroll_employers" (data, status, tenant_id) VALUES (${jsonStr}::jsonb, 'active', 'default') RETURNING id`
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
        sql`SELECT id, data, status, created_at, agent_id, metadata FROM "payroll_employers" WHERE id = ${recordId}`
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

      const validStatuses = ["processed", "pending", "failed", "partial"];
      if (!validStatuses.includes(input.status)) {
        throw new TRPCError({
          code: "BAD_REQUEST",
          message: "Status must be one of: " + validStatuses.join(", "),
        });
      }
      const recordId = input.id;
      const newStatus = input.status;
      await db.execute(
        sql`UPDATE "payroll_employers" SET status = ${newStatus}, updated_at = NOW() WHERE id = ${recordId}`
      );
      return { id: input.id, status: input.status };
    }),

  analytics: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    try {
      const result = await db.execute(
        sql`SELECT status, COUNT(*) as cnt FROM "payroll_employers" GROUP BY status`
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
        name: "Payroll & Salary Disbursement (Go)",
        url: "http://localhost:8251/health",
      },
      {
        name: "Payroll & Salary Disbursement (Rust)",
        url: "http://localhost:8252/health",
      },
      {
        name: "Payroll & Salary Disbursement (Python)",
        url: "http://localhost:8253/health",
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
