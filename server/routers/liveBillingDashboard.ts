import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { platformBillingLedger, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const liveBillingDashboardRouter = router({
  overview: protectedProcedure
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
        .from(platformBillingLedger)
        .orderBy(desc(platformBillingLedger.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platformBillingLedger);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "billing_dash",
        procedure: "overview",
      };
    }),
  transactions: protectedProcedure
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
        .from(platformBillingLedger)
        .orderBy(desc(platformBillingLedger.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platformBillingLedger);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "billing_dash",
        procedure: "transactions",
      };
    }),
  revenue: protectedProcedure
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
        .from(platformBillingLedger)
        .orderBy(desc(platformBillingLedger.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platformBillingLedger);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "billing_dash",
        procedure: "revenue",
      };
    }),
  forecast: protectedProcedure
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
        .from(platformBillingLedger)
        .orderBy(desc(platformBillingLedger.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platformBillingLedger);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "billing_dash",
        procedure: "forecast",
      };
    }),
  export: protectedProcedure
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
        .from(platformBillingLedger)
        .orderBy(desc(platformBillingLedger.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platformBillingLedger);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "billing_dash",
        procedure: "export",
      };
    }),
});
