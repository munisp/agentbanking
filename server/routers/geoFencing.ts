// @ts-nocheck
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";

export const geoFencingRouter = router({
  list: protectedProcedure
    .input(z.object({ limit: z.number().default(20) }).default({}))
    .query(async () => ({ zones: [], total: 0 })),
  getById: protectedProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => ({
      id: input.id,
      name: "",
      coordinates: [],
      active: true,
    })),
  create: protectedProcedure
    .input(
      z.object({
        name: z.string(),
        coordinates: z.array(z.object({ lat: z.number(), lng: z.number() })),
      })
    )
    .mutation(async ({ input }) => ({
      id: "zone-1",
      name: input.name,
      created: true,
    })),
  checkPoint: protectedProcedure
    .input(z.object({ lat: z.number(), lng: z.number() }))
    .query(async () => ({ inZone: false, zones: [] })),
  getStats: protectedProcedure.query(async () => ({
    totalZones: 0,
    activeZones: 0,
    totalChecks: 0,
  })),
});
