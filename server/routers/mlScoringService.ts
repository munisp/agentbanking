import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { fraudMlScores, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const mlScoringServiceRouter = router({
  score: protectedProcedure
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
        .from(fraudMlScores)
        .orderBy(desc(fraudMlScores.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(fraudMlScores);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ml_scoring",
        procedure: "score",
      };
    }),
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
        .from(fraudMlScores)
        .orderBy(desc(fraudMlScores.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(fraudMlScores);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ml_scoring",
        procedure: "models",
      };
    }),
  features: protectedProcedure
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
        .from(fraudMlScores)
        .orderBy(desc(fraudMlScores.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(fraudMlScores);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ml_scoring",
        procedure: "features",
      };
    }),
  history: protectedProcedure
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
        .from(fraudMlScores)
        .orderBy(desc(fraudMlScores.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(fraudMlScores);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ml_scoring",
        procedure: "history",
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
        .from(fraudMlScores)
        .orderBy(desc(fraudMlScores.createdAt))
        .limit(limit)
        .offset(offset);
      const [totalRow] = await db
        .select({ value: count() })
        .from(fraudMlScores);
      return {
        items: rows,
        total: Number(totalRow.value),
        domain: "ml_scoring",
        procedure: "config",
      };
    }),
});
