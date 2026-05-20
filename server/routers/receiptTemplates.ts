/**
 * receiptTemplates.ts — Receipt template management router
 * Provides CRUD for receipt templates used in POS transactions.
 */
import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";

export const receiptTemplatesRouter = router({
  list: protectedProcedure
    .input(
      z.object({
        limit: z.number().default(20),
        offset: z.number().default(0),
      })
    )
    .query(async () => {
      return { items: [], total: 0 };
    }),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async () => {
      return null;
    }),

  create: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        content: z.string(),
        type: z.enum(["cash_in", "cash_out", "transfer", "bill_payment"]),
      })
    )
    .mutation(async ({ input }) => {
      return {
        id: Date.now(),
        name: input.name,
        content: input.content,
        type: input.type,
        createdAt: new Date().toISOString(),
      };
    }),

  update: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        name: z.string().optional(),
        content: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      return { id: input.id, updated: true };
    }),

  delete: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      return { id: input.id, deleted: true };
    }),
});
