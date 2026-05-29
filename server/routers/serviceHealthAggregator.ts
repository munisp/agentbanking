/**
 * Service Health Aggregator — Production Readiness
 *
 * Provides a single endpoint that checks health of all platform services
 * including Go, Rust, and Python microservices, plus infrastructure dependencies.
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

interface ServiceHealth {
  name: string;
  url: string;
  status: "healthy" | "unhealthy" | "degraded" | "unknown";
  latencyMs: number;
  lastChecked: string;
  error?: string;
}

const SERVICE_REGISTRY = [
  // Core API
  { name: "54Link API", url: "http://localhost:3001/api/health" },

  // Go services
  { name: "goAML Integration", url: "http://localhost:8210/health" },
  { name: "KYC Enforcement Gateway", url: "http://localhost:8211/health" },
  { name: "AML Case Manager", url: "http://localhost:8212/health" },
  { name: "Agent Store Service", url: "http://localhost:8220/health" },

  // Rust services
  { name: "CBN KYC Engine", url: "http://localhost:8213/health" },
  { name: "Sanctions Re-Screener", url: "http://localhost:8214/health" },
  { name: "Payment Split Engine", url: "http://localhost:8221/health" },

  // Python services
  { name: "KYC Orchestrator", url: "http://localhost:8215/health" },
  { name: "KYC Event Consumer", url: "http://localhost:8216/health" },
  { name: "Store Analytics Engine", url: "http://localhost:8222/health" },

  // Infrastructure
  { name: "Keycloak", url: "http://localhost:8080/auth/realms/54link" },
  { name: "Temporal", url: "http://localhost:7233/api/v1/namespaces" },
];

async function checkService(service: {
  name: string;
  url: string;
}): Promise<ServiceHealth> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(service.url, { signal: controller.signal });
    clearTimeout(timeout);
    const latencyMs = Date.now() - start;

    return {
      name: service.name,
      url: service.url,
      status: res.ok ? "healthy" : "degraded",
      latencyMs,
      lastChecked: new Date().toISOString(),
    };
  } catch (err: unknown) {
    return {
      name: service.name,
      url: service.url,
      status: "unhealthy",
      latencyMs: Date.now() - start,
      lastChecked: new Date().toISOString(),
      error: err instanceof Error ? err.message : "Connection failed",
    };
  }
}

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

export const serviceHealthAggregatorRouter = router({
  checkAll: protectedProcedure.query(async () => {
    const results = await Promise.all(
      SERVICE_REGISTRY.map(svc => checkService(svc))
    );

    const healthy = results.filter(r => r.status === "healthy").length;
    const unhealthy = results.filter(r => r.status === "unhealthy").length;
    const degraded = results.filter(r => r.status === "degraded").length;

    return {
      summary: {
        total: results.length,
        healthy,
        unhealthy,
        degraded,
        overallStatus:
          unhealthy > 0 ? "critical" : degraded > 0 ? "degraded" : "healthy",
        checkedAt: new Date().toISOString(),
      },
      services: results,
    };
  }),

  checkService: protectedProcedure
    .input(z.object({ name: z.string() }))
    .query(async ({ input }) => {
      const service = SERVICE_REGISTRY.find(
        s => s.name.toLowerCase() === input.name.toLowerCase()
      );
      if (!service) {
        return {
          name: input.name,
          url: "",
          status: "unknown" as const,
          latencyMs: 0,
          lastChecked: new Date().toISOString(),
          error: "Service not found in registry",
        };
      }
      return checkService(service);
    }),

  listServices: protectedProcedure.query(() => {
    return SERVICE_REGISTRY.map(s => ({
      name: s.name,
      url: s.url,
    }));
  }),
});
