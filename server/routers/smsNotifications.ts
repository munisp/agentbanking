import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { notificationDispatchLog, auditLog } from "../../drizzle/schema";
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

export const smsNotificationsRouter = router({
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
        .from(notificationDispatchLog)
        .orderBy(desc(notificationDispatchLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(notificationDispatchLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sms",
        procedure: "list",
      };
    }),
  send: protectedProcedure
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
        action: "sms.send",
        resource: "sms",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "sms",
        action: "send",
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
        .from(notificationDispatchLog)
        .orderBy(desc(notificationDispatchLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(notificationDispatchLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sms",
        procedure: "getById",
      };
    }),
  stats: protectedProcedure
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
        .from(notificationDispatchLog)
        .orderBy(desc(notificationDispatchLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(notificationDispatchLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sms",
        procedure: "stats",
      };
    }),
  balance: protectedProcedure
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
        .from(notificationDispatchLog)
        .orderBy(desc(notificationDispatchLog.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(notificationDispatchLog);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "sms",
        procedure: "balance",
      };
    }),
});
