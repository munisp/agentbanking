// @ts-nocheck
// Round-9 Wave B1b: Orphan-table CRUD — "aml_screening_results" existed in the drizzle schema
// with zero code accessors. Mirrors the sibling *Crud router conventions.
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { amlScreeningResults } from "../../drizzle/schema-stakeholder-tables";
import { eq, desc } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

const listInput = z.object({
  limit: z.number().min(1).max(100).default(50),
  offset: z.number().min(0).default(0),
});

const createInput = z.object({
  tenantId: z.string().uuid(),
  screeningId: z.string().uuid(),
  entityId: z.string().uuid(),
  entityType: z.string().min(1),
  riskLevel: z.enum(["low", "medium", "high", "critical"]),
  riskScore: z.number(),
  matchedWatchlists: z.any().optional(),
  matchedPatterns: z.any().optional(),
  sanctionsHit: z.boolean().optional(),
  pepHit: z.boolean().optional(),
  adverseMediaHit: z.boolean().optional(),
  requiresManualReview: z.boolean().optional(),
  reviewedBy: z.string().uuid().optional(),
  reviewDecision: z.string().optional(),
  reviewNotes: z.string().optional(),
  reviewedAt: z.string().optional(),
  rawResponse: z.any().optional(),
});

const updateInput = createInput.partial().extend({ id: z.string().uuid() });

export const amlScreeningResultsCrudRouter = router({
  list: protectedProcedure.input(listInput).query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const rows = await db
        .select()
        .from(amlScreeningResults)
        .orderBy(desc(amlScreeningResults.id))
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
    .input(z.object({ id: z.string().uuid() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [row] = await db
          .select()
          .from(amlScreeningResults)
          .where(eq(amlScreeningResults.id, input.id))
          .limit(1);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "AML screening result not found",
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
        .insert(amlScreeningResults)
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
        .from(amlScreeningResults)
        .where(eq(amlScreeningResults.id, id))
        .limit(1);
      if (!existing)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "AML screening result not found",
        });
      const [row] = await db
        .update(amlScreeningResults)
        .set(patch as any)
        .where(eq(amlScreeningResults.id, id))
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
    .input(z.object({ id: z.string().uuid() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [existing] = await db
          .select()
          .from(amlScreeningResults)
          .where(eq(amlScreeningResults.id, input.id))
          .limit(1);
        if (!existing)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "AML screening result not found",
          });
        await db.delete(amlScreeningResults).where(eq(amlScreeningResults.id, input.id));
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
