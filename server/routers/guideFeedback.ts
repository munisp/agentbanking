// @ts-nocheck
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";

export const guideFeedbackRouter = router({
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .default({})
    )
    .query(async () => ({ data: [], total: 0 })),

  stats: protectedProcedure.query(async () => ({
    total: 0,
    active: 0,
    pending: 0,
    avgRating: 0,
  })),

  submit: protectedProcedure
    .input(
      z
        .object({
          guideId: z.string().optional(),
          rating: z.number().optional(),
          comment: z.string().optional(),
        })
        .optional()
    )
    .mutation(async () => ({ success: true })),

  summary: protectedProcedure.query(async () => ({
    total: 0,
    breakdown: [],
    lastUpdated: new Date().toISOString(),
  })),

  subsectionStats: protectedProcedure.query(async () => ({
    sections: [],
    avgRating: 0,
    totalResponses: 0,
  })),

  delete: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input }) => ({ deleted: true, id: input.id })),
});
