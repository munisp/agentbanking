import { z } from "zod";
import { router, adminProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, and, gte, sql, count } from "drizzle-orm";
import { apiKeyUsage, apiKeys } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

/**
 * API usage analytics router.
 * Backing tables: apiKeyUsage joined to apiKeys (tenantId via apiKeyId).
 * `byEventType` is derived from apiKeyUsage.method (HTTP method).
 */
export const usageRouter = router({
  stats: adminProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        tenantId: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db)
          return {
            totalEvents: 0,
            byTenant: [],
            byEndpoint: [],
            byEventType: [],
          };
        const since = new Date(Date.now() - input.days * 86400000);
        const conditions = [gte(apiKeyUsage.createdAt, since)];
        if (input.tenantId !== undefined)
          conditions.push(eq(apiKeys.tenantId, input.tenantId));
        const where = and(...conditions);

        const [total] = await db
          .select({ value: count() })
          .from(apiKeyUsage)
          .innerJoin(apiKeys, eq(apiKeyUsage.apiKeyId, apiKeys.id))
          .where(where);

        const byTenant = await db
          .select({
            tenantId: apiKeys.tenantId,
            count: count(),
          })
          .from(apiKeyUsage)
          .innerJoin(apiKeys, eq(apiKeyUsage.apiKeyId, apiKeys.id))
          .where(where)
          .groupBy(apiKeys.tenantId);

        const byEndpoint = await db
          .select({
            endpoint: apiKeyUsage.endpoint,
            count: count(),
          })
          .from(apiKeyUsage)
          .innerJoin(apiKeys, eq(apiKeyUsage.apiKeyId, apiKeys.id))
          .where(where)
          .groupBy(apiKeyUsage.endpoint);

        const byEventType = await db
          .select({
            eventType: apiKeyUsage.method,
            count: count(),
          })
          .from(apiKeyUsage)
          .innerJoin(apiKeys, eq(apiKeyUsage.apiKeyId, apiKeys.id))
          .where(where)
          .groupBy(apiKeyUsage.method);

        return {
          totalEvents: Number(total?.value ?? 0),
          byTenant,
          byEndpoint,
          byEventType,
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

  trends: adminProcedure
    .input(
      z.object({
        days: z.number().min(1).max(90).default(7),
        groupBy: z.enum(["day", "week", "month"]).default("day"),
        tenantId: z.number().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return [];
        const since = new Date(Date.now() - input.days * 86400000);
        const conditions = [gte(apiKeyUsage.createdAt, since)];
        if (input.tenantId !== undefined)
          conditions.push(eq(apiKeys.tenantId, input.tenantId));
        const where = and(...conditions);

        const rows = await db
          .select({
            date: sql<string>`date_trunc('${sql.raw(input.groupBy)}', ${apiKeyUsage.createdAt})::date::text`,
            count: count(),
            uniqueTenants: sql<number>`COUNT(DISTINCT ${apiKeys.tenantId})`,
          })
          .from(apiKeyUsage)
          .innerJoin(apiKeys, eq(apiKeyUsage.apiKeyId, apiKeys.id))
          .where(where)
          .groupBy(
            sql`date_trunc('${sql.raw(input.groupBy)}', ${apiKeyUsage.createdAt})`
          )
          .orderBy(
            sql`date_trunc('${sql.raw(input.groupBy)}', ${apiKeyUsage.createdAt})`
          );

        return rows.map(r => ({
          date: r.date,
          count: Number(r.count),
          uniqueTenants: Number(r.uniqueTenants),
        }));
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
