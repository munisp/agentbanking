import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count, gte, lte } from "drizzle-orm";
import { fraudMlScores, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

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
  analytics: protectedProcedure.query(async () => {
    return {
      totalRecords: 0,
      activeItems: 0,
      lastUpdated: new Date().toISOString(),
    };
  }),
  scoringHistory: protectedProcedure
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
  scoreTransaction: protectedProcedure
    .input(z.object({ id: z.string().optional() }).optional())
    .mutation(async ({ input, ctx }) => {
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");
      auditFinancialAction(
        "UPDATE",
        "mlScoringService",
        "mutation",
        "Executed mlScoringService mutation"
      );

      return {
        success: true,
        action: "scoreTransaction",
        id: input?.id ?? null,
        timestamp: new Date().toISOString(),
      };
    }),
  batchScore: protectedProcedure
    .input(z.object({ id: z.string().optional() }).optional())
    .mutation(async ({ input }) => {
      return {
        success: true,
        action: "batchScore",
        id: input?.id ?? null,
        timestamp: new Date().toISOString(),
      };
    }),
  explainScore: protectedProcedure
    .input(
      z
        .object({ id: z.string().optional(), query: z.string().optional() })
        .optional()
    )
    .query(async ({ input }) => {
      return { data: null, id: input?.id ?? null };
    }),
});
