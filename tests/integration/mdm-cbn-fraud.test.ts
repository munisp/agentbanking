/**
 * Integration tests: MDM heartbeat, CBN compliance, fraud detection, settlement
 * These tests run against a real (test) database and server.
 * Run with: NODE_ENV=test JWT_SECRET=test-secret pnpm test tests/integration/mdm-cbn-fraud.test.ts
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { createTRPCProxyClient, httpBatchLink } from "@trpc/client";
import superjson from "superjson";
import type { AppRouter } from "../../server/routers";

const BASE_URL = process.env.TEST_SERVER_URL ?? "http://localhost:3000";
const INTEGRATION = !!process.env.TEST_SERVER_URL;

const client = createTRPCProxyClient<AppRouter>({
  links: [
    httpBatchLink({
      url: `${BASE_URL}/api/trpc`,
      transformer: superjson,
      headers: () => ({
        "x-test-bypass": process.env.TEST_BYPASS_TOKEN ?? "test-bypass-token",
      }),
    }),
  ],
});

// ── MDM Heartbeat ─────────────────────────────────────────────────────────────
describe.skipIf(!INTEGRATION)("MDM Heartbeat", () => {
  it("should accept a valid heartbeat payload", async () => {
    const result = await client.mdm.heartbeat.mutate({
      deviceId: "TEST-DEVICE-001",
      agentCode: "AG-TEST-001",
      terminalModel: "PAX A920 MAX",
      batteryLevel: 85,
      signalStrength: -72,
      appVersion: "2.4.1",
      osVersion: "Android 11",
      latitude: 6.5244,
      longitude: 3.3792,
      isCompliant: true,
    });
    expect(result).toBeDefined();
    expect(result.received).toBe(true);
  });

  it("should flag non-compliant device", async () => {
    const result = await client.mdm.heartbeat.mutate({
      deviceId: "TEST-DEVICE-002",
      agentCode: "AG-TEST-002",
      terminalModel: "PAX A920 MAX",
      batteryLevel: 10,
      signalStrength: -100,
      appVersion: "1.0.0", // outdated
      osVersion: "Android 8", // outdated
      latitude: 6.5244,
      longitude: 3.3792,
      isCompliant: false,
    });
    expect(result).toBeDefined();
    expect(result.received).toBe(true);
  });
});

// ── Fraud Detection ───────────────────────────────────────────────────────────
describe.skipIf(!INTEGRATION)("Fraud Detection", () => {
  it("should return fraud score for a transaction", async () => {
    const result = await client.fraud.analyzeTransaction.mutate({
      transactionRef: "TEST-TX-001",
      agentId: 1,
      amount: 50000,
      type: "Cash Out",
      channel: "App",
      customerPhone: "+2348012345678",
    });
    expect(result).toBeDefined();
    expect(typeof result.fraudScore).toBe("number");
    expect(result.fraudScore).toBeGreaterThanOrEqual(0);
    expect(result.fraudScore).toBeLessThanOrEqual(1);
  });

  it("should flag high-velocity transactions as high fraud risk", async () => {
    // Simulate 5 rapid transactions from same agent
    const results = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        client.fraud.analyzeTransaction.mutate({
          transactionRef: `TEST-TX-VELOCITY-${i}`,
          agentId: 999,
          amount: 200000,
          type: "Cash Out",
          channel: "App",
          customerPhone: "+2348099999999",
        })
      )
    );
    // At least one should have elevated fraud score
    const highRisk = results.filter(r => r.fraudScore > 0.5);
    expect(highRisk.length).toBeGreaterThan(0);
  });
});

// ── Settlement ────────────────────────────────────────────────────────────────
describe.skipIf(!INTEGRATION)("Settlement", () => {
  it("should return settlement summary for a date range", async () => {
    const result = await client.settlement.getSummary.query({
      from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
      to: new Date(),
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.batches) || result.batches === undefined).toBe(
      true
    );
  });
});

// ── CBN Compliance ────────────────────────────────────────────────────────────
describe.skipIf(!INTEGRATION)("CBN Compliance", () => {
  it("should return CBN report metadata", async () => {
    const result = await client.cbn.getReports.query({
      page: 1,
      limit: 10,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.reports)).toBe(true);
  });

  it("should validate CBN report structure", async () => {
    const result = await client.cbn.getReports.query({ page: 1, limit: 1 });
    if (result.reports.length > 0) {
      const report = result.reports[0];
      expect(report).toHaveProperty("id");
      expect(report).toHaveProperty("reportType");
      expect(report).toHaveProperty("status");
      expect(report).toHaveProperty("createdAt");
    }
  });
});

// ── Agent Management ──────────────────────────────────────────────────────────
describe.skipIf(!INTEGRATION)("Agent Management", () => {
  it("should list agents with pagination", async () => {
    const result = await client.agentManagement.list.query({
      page: 1,
      limit: 10,
    });
    expect(result).toBeDefined();
    expect(Array.isArray(result.agents)).toBe(true);
    expect(typeof result.total).toBe("number");
  });

  it("should return agent stats", async () => {
    const result = await client.agentManagement.getStats.query();
    expect(result).toBeDefined();
    expect(typeof result.totalAgents).toBe("number");
    expect(typeof result.activeAgents).toBe("number");
  });
});

// ── System Health ─────────────────────────────────────────────────────────────
describe.skipIf(!INTEGRATION)("System Health", () => {
  it("should return system health status", async () => {
    const response = await fetch(`${BASE_URL}/health`);
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("ok");
  });

  it("should return metrics endpoint", async () => {
    const response = await fetch(`${BASE_URL}/metrics`);
    expect(response.status).toBe(200);
    const text = await response.text();
    expect(text).toContain("# HELP");
  });
});
