// @ts-nocheck
// Round-9 Wave B1b: Orphan-table CRUD — "agent_float_insurance_claims" existed in the drizzle schema
// with zero code accessors. Mirrors the sibling *Crud router conventions.
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { agentFloatInsuranceClaims } from "../../drizzle/schema-stakeholder-tables";
import { eq, desc } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

const listInput = z.object({
  limit: z.number().min(1).max(100).default(50),
  offset: z.number().min(0).default(0),
});

const createInput = z.object({
  tenantId: z.string().uuid(),
  agentId: z.string().uuid(),
  floatAccountId: z.string().uuid(),
  claimAmount: z.number(),
  approvedAmount: z.number().optional(),
  status: z.enum(["submitted", "under_review", "approved", "rejected", "paid"]).optional(),
  incidentDate: z.string(),
  description: z.string().min(1),
  evidenceUrls: z.array(z.string()).optional(),
  reviewedBy: z.string().uuid().optional(),
  reviewNotes: z.string().optional(),
  paidAt: z.string().optional(),
});

const updateInput = createInput.partial().extend({ id: z.string().uuid() });

export const agentFloatInsuranceClaimsCrudRouter = router({
  list: protectedProcedure.input(listInput).query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const rows = await db
        .select()
        .from(agentFloatInsuranceClaims)
        .orderBy(desc(agentFloatInsuranceClaims.id))
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
          .from(agentFloatInsuranceClaims)
          .where(eq(agentFloatInsuranceClaims.id, input.id))
          .limit(1);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Float insurance claim not found",
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
        .insert(agentFloatInsuranceClaims)
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
        .from(agentFloatInsuranceClaims)
        .where(eq(agentFloatInsuranceClaims.id, id))
        .limit(1);
      if (!existing)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Float insurance claim not found",
        });
      const [row] = await db
        .update(agentFloatInsuranceClaims)
        .set(patch as any)
        .where(eq(agentFloatInsuranceClaims.id, id))
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
          .from(agentFloatInsuranceClaims)
          .where(eq(agentFloatInsuranceClaims.id, input.id))
          .limit(1);
        if (!existing)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Float insurance claim not found",
          });
        await db.delete(agentFloatInsuranceClaims).where(eq(agentFloatInsuranceClaims.id, input.id));
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
