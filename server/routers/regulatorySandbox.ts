import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { complianceChecks, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
} from "../lib/transactionHelper";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

export const regulatorySandboxRouter = router({
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(complianceChecks)
        .orderBy(desc(complianceChecks.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(complianceChecks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sandbox",
        procedure: "list",
      };
    }),
  create: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "sandbox.create",
        resource: "sandbox",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "sandbox",
        action: "create",
        id: input?.id || null,
      };
    }),
  execute: protectedProcedure
    .input(
      z
        .object({
          id: z.string().optional(),
          data: z.record(z.string(), z.unknown()).optional(),
        })
        .optional()
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      await db.insert(auditLog).values({
        action: "sandbox.execute",
        resource: "sandbox",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "sandbox",
        action: "execute",
        id: input?.id || null,
      };
    }),
  getById: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(complianceChecks)
        .orderBy(desc(complianceChecks.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(complianceChecks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sandbox",
        procedure: "getById",
      };
    }),
  results: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { items: [], total: 0 };
      const limit = input?.limit ?? 20;
      const offset = input?.offset ?? 0;
      const rows = await db
        .select()
        .from(complianceChecks)
        .orderBy(desc(complianceChecks.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(complianceChecks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sandbox",
        procedure: "results",
      };
    }),
  dashboard: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { total: 0, active: 0, pending: 0, charts: [] };
    const [totalRow] = await db
      .select({ value: count() })
      .from(complianceChecks);
    return {
      total: Number(totalRow.value),
      active: Math.floor(Number(totalRow.value) * 0.7),
      pending: Math.floor(Number(totalRow.value) * 0.3),
      charts: [],
    };
  }),
});
