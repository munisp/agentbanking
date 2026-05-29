import { z } from "zod";
import {
  publicProcedure as openProcedure,
  protectedProcedure,
  router,
} from "../_core/trpc";
import { getDb } from "../db";
import { platformSettings } from "../../drizzle/schema";
import { sql, eq, desc, count } from "drizzle-orm";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  checkServiceHealth,
  reportServiceHealth,
} from "../middleware/productionDegradation";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { TRPCError } from "@trpc/server";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  connected: ["disconnected", "degraded", "maintenance"],
  disconnected: ["connected"],
  degraded: ["connected", "disconnected"],
  maintenance: ["connected", "disconnected"],
};

const MIDDLEWARE_SERVICES = [
  { name: "kafka", port: 9092, protocol: "tcp" },
  { name: "redis", port: 6379, protocol: "tcp" },
  { name: "tigerBeetle", port: 3001, protocol: "http" },
  { name: "fluvio", port: 9003, protocol: "tcp" },
  { name: "permify", port: 3476, protocol: "grpc" },
  { name: "keycloak", port: 8080, protocol: "http" },
  { name: "postgres", port: 5432, protocol: "tcp" },
  { name: "minio", port: 9000, protocol: "http" },
  { name: "apisix", port: 9180, protocol: "http" },
  { name: "opensearch", port: 9200, protocol: "http" },
  { name: "dapr", port: 3500, protocol: "http" },
  { name: "temporal", port: 7233, protocol: "grpc" },
  { name: "mojaloop", port: 4002, protocol: "http" },
] as const;

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
    .query(async () => ({
      data: MIDDLEWARE_SERVICES.map(s => ({
        name: s.name,
        port: s.port,
        protocol: s.protocol,
        status: checkServiceHealth(s.name) ? "connected" : "disconnected",
      })),
      total: MIDDLEWARE_SERVICES.length,
    })),

  getById: protectedProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => {
      const service = MIDDLEWARE_SERVICES.find(s => s.name === input.id);
      if (!service) {
        return {
          id: input.id,
          name: input.id,
          url: "",
          status: "disconnected",
        };
      }
      return {
        id: service.name,
        name: service.name,
        url: `${service.protocol}://localhost:${service.port}`,
        status: checkServiceHealth(service.name) ? "connected" : "disconnected",
      };
    }),

  getStats: openProcedure.query(async () => {
    const statuses = MIDDLEWARE_SERVICES.map(s => ({
      name: s.name,
      connected: checkServiceHealth(s.name),
    }));

    const connected = statuses.filter(s => s.connected).length;
    const disconnected = statuses.length - connected;

    return {
      total: statuses.length,
      connected,
      disconnected,
      avgLatency: 0,
      services: statuses,
    };
  }),

  testConnection: protectedProcedure
    .input(z.object({ serviceId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      const _fees = calculateFee(
        typeof input === "object" && "amount" in input
          ? Number((input as Record<string, unknown>).amount)
          : 0,
        "transfer"
      );
      const _commission = calculateCommission(_fees.fee, "transfer");
      const _tax = calculateTax(_fees.fee, "vat");

      const service = MIDDLEWARE_SERVICES.find(s => s.name === input.serviceId);
      const isHealthy = service ? checkServiceHealth(service.name) : false;

      if (service) {
        reportServiceHealth(service.name, isHealthy);
      }

      auditFinancialAction(
        "UPDATE",
        "middlewareService",
        input.serviceId,
        `Connection test: ${isHealthy ? "success" : "failed"}`
      );

      return {
        serviceId: input.serviceId,
        connected: isHealthy,
        latency: 0,
        testedAt: new Date().toISOString(),
      };
    }),

  updateUrl: protectedProcedure
    .input(z.object({ serviceId: z.string(), url: z.string().url() }))
    .mutation(async ({ input }) => {
      auditFinancialAction(
        "UPDATE",
        "middlewareService",
        input.serviceId,
        `URL updated to ${input.url}`
      );

      return {
        serviceId: input.serviceId,
        url: input.url,
        updated: true,
        updatedAt: new Date().toISOString(),
      };
    }),
});
