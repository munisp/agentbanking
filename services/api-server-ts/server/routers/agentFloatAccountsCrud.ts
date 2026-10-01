// @ts-nocheck
// Round-9 Wave B1b: Orphan-table CRUD — "agent_float_accounts" existed in the drizzle schema
// with zero code accessors. Mirrors the sibling *Crud router conventions.
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { agentFloatAccounts } from "../../drizzle/schema-stakeholder-tables";
import { eq, desc } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

const listInput = z.object({
  limit: z.number().min(1).max(100).default(50),
  offset: z.number().min(0).default(0),
});

const createInput = z.object({
  tenantId: z.string().uuid(),
  agentId: z.string().uuid(),
  currency: z.string().optional(),
  balance: z.number().optional(),
  reservedBalance: z.number().optional(),
  creditLimit: z.number().optional(),
  status: z.enum(["active", "suspended", "closed", "overdrawn"]).optional(),
  tbAccountId: z.string().optional(),
  lastReconciledAt: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
});

const updateInput = createInput.partial().extend({ id: z.string().uuid() });

export const agentFloatAccountsCrudRouter = router({
  list: protectedProcedure.input(listInput).query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const rows = await db
        .select()
        .from(agentFloatAccounts)
        .orderBy(desc(agentFloatAccounts.id))
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
          .from(agentFloatAccounts)
          .where(eq(agentFloatAccounts.id, input.id))
          .limit(1);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Agent float account not found",
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
        .insert(agentFloatAccounts)
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
        .from(agentFloatAccounts)
        .where(eq(agentFloatAccounts.id, id))
        .limit(1);
      if (!existing)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Agent float account not found",
        });
      const [row] = await db
        .update(agentFloatAccounts)
        .set(patch as any)
        .where(eq(agentFloatAccounts.id, id))
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
          .from(agentFloatAccounts)
          .where(eq(agentFloatAccounts.id, input.id))
          .limit(1);
        if (!existing)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Agent float account not found",
          });
        await db.delete(agentFloatAccounts).where(eq(agentFloatAccounts.id, input.id));
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
