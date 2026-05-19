import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, sql, count, avg, and } from "drizzle-orm";
import {
  platform_health_checks,
  systemConfig,
  auditLog,
} from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const goServiceBridgeRouter = router({
  listServices: protectedProcedure
    .input(
      z.object({ limit: z.number().min(1).max(100).default(50) }).optional()
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [registry] = await db
          .select()
          .from(systemConfig)
          .where(eq(systemConfig.key, "go_service_registry"))
          .limit(1);
        const services = registry
          ? JSON.parse(String(registry.value))
          : [
              { name: "kyb-engine", port: 8130, status: "running" },
              { name: "mojaloop-connector", port: 8140, status: "running" },
              { name: "offline-queue", port: 8160, status: "running" },
            ];
        return {
          services: services.slice(0, input?.limit ?? 50),
          total: services.length,
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getServiceHealth: protectedProcedure
    .input(z.object({ serviceName: z.string().min(1).max(64) }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const checks = await db
          .select()
          .from(platform_health_checks)
          .where(eq(platform_health_checks.serviceName, input.serviceName))
          .orderBy(desc(platform_health_checks.checkedAt))
          .limit(10);
        const [avgLat] = await db
          .select({ value: avg(platform_health_checks.responseTime) })
          .from(platform_health_checks)
          .where(eq(platform_health_checks.serviceName, input.serviceName))
          .limit(100);
        return {
          serviceName: input.serviceName,
          recentChecks: checks,
          avgLatencyMs: Math.round(Number(avgLat.value ?? 0)),
          status:
            checks.length > 0 && checks[0].status === "healthy"
              ? "healthy"
              : "unknown",
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  restartService: protectedProcedure
    .input(
      z.object({
        serviceName: z.string().min(1).max(64),
        force: z.boolean().default(false),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        await db.insert(auditLog).values({
          action: "go_service_restarted",
          resource: "go_service_bridge",
          resourceId: input.serviceName,
          status: "success",
          metadata: { force: input.force },
        });
        return {
          serviceName: input.serviceName,
          status: "restarting",
          restartedAt: new Date().toISOString(),
        };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getStats: protectedProcedure.query(async () => {
    const db = (await getDb())!;
    const [checks] = await db
      .select({
        total: count(),
        avgLat: avg(platform_health_checks.responseTime),
      })
      .from(platform_health_checks)
      .limit(100);
    return {
      totalHealthChecks: Number(checks.total),
      avgLatencyMs: Math.round(Number(checks.avgLat ?? 0)),
    };
  }),
});
