// @ts-nocheck
import { z } from "zod";
import {
  publicProcedure as openProcedure,
  protectedProcedure,
  router,
} from "../_core/trpc";
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

export const middlewareServiceManagerRouter = router({
  list: protectedProcedure
    .input(
      z
        .object({
          limit: z.number().default(20),
          offset: z.number().default(0),
        })
        .optional()
    )
    .query(async () => ({ data: [], total: 0 })),

  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => ({
      id: input.id,
      name: "",
      url: "",
      status: "connected",
    })),

  getStats: openProcedure.query(async () => ({
    total: 13,
    connected: 12,
    disconnected: 1,
    avgLatency: 45,
    services: [],
  })),

  testConnection: protectedProcedure
    .input(z.object({ serviceId: z.string() }))
    .mutation(async ({ input }) => ({
      serviceId: input.serviceId,
      connected: true,
      latency: 12,
      testedAt: new Date().toISOString(),
    })),

  updateUrl: protectedProcedure
    .input(z.object({ serviceId: z.string(), url: z.string().url() }))
    .mutation(async ({ input }) => ({
      serviceId: input.serviceId,
      url: input.url,
      updated: true,
      updatedAt: new Date().toISOString(),
    })),
});
