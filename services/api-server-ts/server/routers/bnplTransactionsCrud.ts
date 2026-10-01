// @ts-nocheck
// Round-9 Wave B1b: Orphan-table CRUD — "bnpl_transactions" existed in the drizzle schema
// with zero code accessors. Mirrors the sibling *Crud router conventions.
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { bnplTransactions } from "../../drizzle/schema-stakeholder-tables";
import { eq, desc } from "drizzle-orm";
import { TRPCError } from "@trpc/server";

const listInput = z.object({
  limit: z.number().min(1).max(100).default(50),
  offset: z.number().min(0).default(0),
});

const createInput = z.object({
  tenantId: z.string().uuid(),
  customerId: z.string().uuid(),
  merchantId: z.string().uuid(),
  originalTransactionId: z.string().uuid().optional(),
  principalAmount: z.number(),
  totalRepayableAmount: z.number(),
  outstandingBalance: z.number(),
  interestRate: z.number().optional(),
  tenorDays: z.number().int(),
  installmentCount: z.number().int().optional(),
  installmentAmount: z.number(),
  status: z.enum(["initiated", "approved", "active", "partially_repaid", "fully_repaid", "overdue", "defaulted", "cancelled"]).optional(),
  approvedAt: z.string().optional(),
  firstInstallmentDueDate: z.string().optional(),
  lastInstallmentDueDate: z.string().optional(),
  defaultedAt: z.string().optional(),
  tbDebitAccountId: z.string().optional(),
  tbCreditAccountId: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
});

const updateInput = createInput.partial().extend({ id: z.string().uuid() });

export const bnplTransactionsCrudRouter = router({
  list: protectedProcedure.input(listInput).query(async ({ input }) => {
    try {
      const db = (await getDb())!;
      const rows = await db
        .select()
        .from(bnplTransactions)
        .orderBy(desc(bnplTransactions.id))
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
          .from(bnplTransactions)
          .where(eq(bnplTransactions.id, input.id))
          .limit(1);
        if (!row)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "BNPL transaction not found",
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
        .insert(bnplTransactions)
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
        .from(bnplTransactions)
        .where(eq(bnplTransactions.id, id))
        .limit(1);
      if (!existing)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "BNPL transaction not found",
        });
      const [row] = await db
        .update(bnplTransactions)
        .set(patch as any)
        .where(eq(bnplTransactions.id, id))
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
          .from(bnplTransactions)
          .where(eq(bnplTransactions.id, input.id))
          .limit(1);
        if (!existing)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "BNPL transaction not found",
          });
        await db.delete(bnplTransactions).where(eq(bnplTransactions.id, input.id));
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
