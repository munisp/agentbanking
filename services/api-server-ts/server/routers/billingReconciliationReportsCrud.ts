// @ts-nocheck
// Round-9 Wave B1b: Orphan-table CRUD — "billing_reconciliation_reports" existed in the drizzle schema
// with zero code accessors. Mirrors the sibling *Crud router conventions.
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { billingReconciliationReports } from "../../drizzle/schema";
import { eq, desc } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

const listInput = z.object({
  limit: z.number().min(1).max(100).default(50),
  offset: z.number().min(0).default(0),
});

const createInput = z.object({
  reportPeriod: z.string().max(20),
  periodStart: z.string(),
  periodEnd: z.string(),
  billingModel: z.enum(["revenue_share", "subscription", "hybrid"]),
  status: z.enum(["pending", "matched", "discrepancy", "resolved"]).optional(),
  projectedTransactions: z.number().int().optional(),
  projectedGrossVolume: z.number().optional(),
  projectedPlatformRevenue: z.number().optional(),
  projectedClientRevenue: z.number().optional(),
  projectedAgents: z.number().int().optional(),
  projectedTxPerAgent: z.number().optional(),
  actualTransactions: z.number().int().optional(),
  actualGrossVolume: z.number().optional(),
  actualPlatformRevenue: z.number().optional(),
  actualClientRevenue: z.number().optional(),
  actualAgents: z.number().int().optional(),
  actualTxPerAgent: z.number().optional(),
  revenueVariancePct: z.number().optional(),
  volumeVariancePct: z.number().optional(),
  agentVariancePct: z.number().optional(),
  insights: z.any().optional(),
  generatedBy: z.string().max(64).optional(),
  approvedBy: z.string().max(64).optional(),
  approvedAt: z.string().optional(),
});

const updateInput = createInput.partial().extend({ id: z.number() });

export const billingReconciliationReportsCrudRouter = router({
  list: protectedProcedure.input(listInput).query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const rows = await db
        .select()
        .from(billingReconciliationReports)
        .orderBy(desc(billingReconciliationReports.id))
        .limit(input.limit)
        .offset(input.offset);
      return { items: rows, total: rows.length };
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .select()
          .from(billingReconciliationReports)
          .where(eq(billingReconciliationReports.id, input.id))
          .limit(1);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Billing reconciliation report not found",
          });
        return row;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  create: protectedProcedure.input(createInput).mutation(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const [row] = await db
        .insert(billingReconciliationReports)
        .values(input as any)
        .returning();
      return row;
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),
  update: protectedProcedure.input(updateInput).mutation(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const { id, ...patch } = input;
      const [existing] = await db
        .select()
        .from(billingReconciliationReports)
        .where(eq(billingReconciliationReports.id, id))
        .limit(1);
      if (!existing)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Billing reconciliation report not found",
        });
      const [row] = await db
        .update(billingReconciliationReports)
        .set(patch as any)
        .where(eq(billingReconciliationReports.id, id))
        .returning();
      return row;
    } catch (error) {
      if (error instanceof TRPCError) throw error;
      throw new TRPCError({
        code: "INTERNAL_SERVER_ERROR",
        message: error instanceof Error ? error.message : "Internal server error",
      });
    }
  }),
  remove: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [existing] = await db
          .select()
          .from(billingReconciliationReports)
          .where(eq(billingReconciliationReports.id, input.id))
          .limit(1);
        if (!existing)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Billing reconciliation report not found",
          });
        await db.delete(billingReconciliationReports).where(eq(billingReconciliationReports.id, input.id));
        return { success: true, deleted: input.id };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
