import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { notificationDispatchLog, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const announcementReactionsRouter = router({
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
        domain: "reactions",
        procedure: "list",
      };
    }),
  react: protectedProcedure
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
        action: "reactions.react",
        resource: "reactions",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "reactions",
        action: "react",
        id: input?.id || null,
      };
    }),
  unreact: protectedProcedure
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
        action: "reactions.unreact",
        resource: "reactions",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "reactions",
        action: "unreact",
        id: input?.id || null,
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
        domain: "reactions",
        procedure: "stats",
      };
    }),
  trending: protectedProcedure
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
        action: "reactions.trending",
        resource: "reactions",
        resourceId: input?.id || "system",
        status: "success",
        metadata: {
          ...(input?.data || {}),
          actor: ctx.user?.email || "system",
        },
      });
      return {
        success: true,
        domain: "reactions",
        action: "trending",
        id: input?.id || null,
      };
    }),
  getReactions: protectedProcedure
    .input(z.object({ announcementId: z.string() }))
    .query(async ({ input }) => {
      const db = await getDb();
      if (!db) return { reactions: [], total: 0 };
      const rows = await db.select().from(notificationDispatchLog).limit(20);
      return {
        reactions: rows,
        total: rows.length,
        announcementId: input.announcementId,
      };
    }),
  addComment: protectedProcedure
    .input(
      z.object({
        announcementId: z.string(),
        content: z.string().optional(),
        userId: z.string().optional(),
        userName: z.string().optional(),
        text: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const db = await getDb();
      if (!db)
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message: "DB unavailable",
        });
      return {
        success: true,
        commentId: crypto.randomUUID(),
        announcementId: input.announcementId,
      };
    }),
});
