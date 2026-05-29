import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { auditLog, platform_health_checks } from "../../drizzle/schema";
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

export const artRobustnessRouter = router({
  models: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "art_robust",
        procedure: "models",
      };
    }),
  attack: protectedProcedure
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
        action: "art_robust.attack",
        resource: "art_robust",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "art_robust",
        action: "attack",
        id: input?.id || null,
      };
    }),
  defense: protectedProcedure
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
        action: "art_robust.defense",
        resource: "art_robust",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "art_robust",
        action: "defense",
        id: input?.id || null,
      };
    }),
  report: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "art_robust",
        procedure: "report",
      };
    }),
  config: protectedProcedure
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
        .from(platform_health_checks)
        .orderBy(desc((platform_health_checks as any).createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(platform_health_checks);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "art_robust",
        procedure: "config",
      };
    }),
  health: protectedProcedure.query(async () => {
    return {
      status: "healthy",
      uptime: process.uptime(),
      memory: process.memoryUsage().heapUsed,
      timestamp: new Date().toISOString(),
    };
  }),
  analytics: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeItems: 0,
      lastUpdated: new Date().toISOString(),
    };
  }),
  listAttacks: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      return { items: [], total: 0 };
    }),
  listResults: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async ({ input }) => {
      return { items: [], total: 0 };
    }),
  runAttack: protectedProcedure
    .input(z.object({ id: z.string().optional() }).optional())
    .mutation(async ({ input }) => {
      return {
        success: true,
        action: "runAttack",
        id: input?.id ?? null,
        timestamp: new Date().toISOString(),
      };
    }),
  runFullSuite: protectedProcedure
    .input(z.object({ id: z.string().optional() }).optional())
    .mutation(async ({ input }) => {
      return {
        success: true,
        action: "runFullSuite",
        id: input?.id ?? null,
        timestamp: new Date().toISOString(),
      };
    }),
});
