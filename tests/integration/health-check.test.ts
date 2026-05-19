/**
 * Integration Test: Health Check & Service Discovery
 * Verifies the health check router reports correct service status.
 */
import { describe, it, expect, vi } from "vitest";
import { appRouter } from "../../server/routers";
import type { TrpcContext } from "../../server/_core/context";

vi.mock("../../server/db", () => ({
  getDb: vi.fn().mockResolvedValue(null),
}));

const mockCtx: TrpcContext = {
  user: { id: "admin-1", role: "admin", tenantId: "tenant-1" },
  req: {} as any,
  res: {} as any,
};

const caller = appRouter.createCaller(mockCtx);

describe("Health Check Integration", () => {
  it("status returns service health with timestamps", async () => {
    const result = await caller.healthCheck.status();
    expect(result.timestamp).toBeDefined();
    expect(result.uptime).toBeGreaterThanOrEqual(0);
    expect(result.services).toBeDefined();
    expect(result.services.database).toBeDefined();
    expect(result.totalServices).toBeGreaterThan(0);
  });

  it("microservices returns service list", async () => {
    const result = await caller.healthCheck.microservices();
    expect(result.services).toBeDefined();
    expect(Array.isArray(result.services)).toBe(true);
    expect(result.services.length).toBeGreaterThan(0);
    for (const svc of result.services) {
      expect(svc.name).toBeDefined();
      expect(svc.type).toBeDefined();
      expect(svc.port).toBeDefined();
      expect(["healthy", "unhealthy", "unavailable"]).toContain(svc.status);
    }
  });
});
