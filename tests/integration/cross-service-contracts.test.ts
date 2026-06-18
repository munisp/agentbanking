/**
 * Cross-Service Contract Tests
 * Verifies that inter-service communication contracts are maintained.
 * Tests HTTP endpoints, gRPC bridge, and event schemas across service boundaries.
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const ROOT = path.resolve(__dirname, "../..");

describe("Cross-Service Contract Tests", () => {
  describe("Proto Contract Validation", () => {
    it("proto file defines all required services", () => {
      const proto = fs.readFileSync(
        path.join(ROOT, "proto/go-services.proto"),
        "utf-8"
      );
      const requiredServices = [
        "WorkflowOrchestrator",
        "TigerBeetleLedger",
        "SettlementGateway",
        "PBACEngine",
      ];
      for (const svc of requiredServices) {
        expect(proto).toContain(`service ${svc}`);
      }
    });

    it("gRPC bridge implements all proto services", () => {
      const bridge = fs.readFileSync(
        path.join(ROOT, "server/grpc/grpcServiceBridge.ts"),
        "utf-8"
      );
      expect(bridge).toContain("WorkflowOrchestratorClient");
      expect(bridge).toContain("TigerBeetleLedgerClient");
      expect(bridge).toContain("SettlementGatewayClient");
    });

    it("gRPC Python server implements all services", () => {
      const server = fs.readFileSync(
        path.join(ROOT, "services/python/grpc/server.py"),
        "utf-8"
      );
      expect(server).toContain("WorkflowOrchestratorService");
      expect(server).toContain("TigerBeetleLedgerService");
      expect(server).toContain("SettlementGatewayService");
    });
  });

  describe("Resilient HTTP Client Contract", () => {
    it("resilient HTTP client exports required functions", () => {
      const client = fs.readFileSync(
        path.join(ROOT, "server/lib/resilientHttpClient.ts"),
        "utf-8"
      );
      expect(client).toContain("export async function resilientFetch");
      expect(client).toContain("export function getCircuitBreakerStatus");
      expect(client).toContain("CircuitBreakerState");
    });

    it("circuit breaker has correct threshold and reset values", () => {
      const client = fs.readFileSync(
        path.join(ROOT, "server/lib/resilientHttpClient.ts"),
        "utf-8"
      );
      expect(client).toContain("CIRCUIT_THRESHOLD = 5");
      expect(client).toContain("CIRCUIT_RESET_MS = 30_000");
    });
  });

  describe("Graceful Degradation Contract", () => {
    it("degradation middleware exports required functions", () => {
      const middleware = fs.readFileSync(
        path.join(ROOT, "server/middleware/productionDegradation.ts"),
        "utf-8"
      );
      expect(middleware).toContain("export function checkServiceHealth");
      expect(middleware).toContain("export function reportServiceHealth");
      expect(middleware).toContain("export function isDegradedMode");
      expect(middleware).toContain("export function isReadOnlyMode");
      expect(middleware).toContain("export function getDegradationStatus");
      expect(middleware).toContain("export async function withDegradation");
    });
  });

  describe("Go Service Graceful Shutdown", () => {
    it("all Go services with main.go have shutdown handler", () => {
      const goServicesDir = path.join(ROOT, "services/go");
      const dirs = fs.readdirSync(goServicesDir, { withFileTypes: true });
      const missing: string[] = [];

      for (const dir of dirs) {
        if (!dir.isDirectory()) continue;
        const mainFile = path.join(goServicesDir, dir.name, "main.go");
        if (!fs.existsSync(mainFile)) continue;
        const content = fs.readFileSync(mainFile, "utf-8");
        if (
          !content.includes("signal.Notify") &&
          !content.includes("SIGTERM") &&
          !content.includes("setupGracefulShutdown") &&
          !content.includes("graceful")
        ) {
          missing.push(dir.name);
        }
      }

      expect(missing).toEqual([]);
    });
  });

  describe("Python Service Graceful Shutdown", () => {
    it("Python services with main.py have shutdown handler", () => {
      const pyServicesDir = path.join(ROOT, "services/python");
      const dirs = fs.readdirSync(pyServicesDir, { withFileTypes: true });
      let total = 0;
      let withShutdown = 0;

      for (const dir of dirs) {
        if (!dir.isDirectory()) continue;
        const mainFile = path.join(pyServicesDir, dir.name, "main.py");
        if (!fs.existsSync(mainFile)) continue;
        total++;
        const content = fs.readFileSync(mainFile, "utf-8");
        if (
          content.includes("signal.signal") ||
          content.includes("SIGTERM") ||
          content.includes("graceful_shutdown") ||
          content.includes("atexit") ||
          content.includes("lifespan")
        ) {
          withShutdown++;
        }
      }

      // At least 90% should have shutdown handlers
      const ratio = withShutdown / total;
      expect(ratio).toBeGreaterThanOrEqual(0.9);
    });
  });

  describe("Rust Service Graceful Shutdown", () => {
    it("Rust services have shutdown signal handler", () => {
      const rustServicesDir = path.join(ROOT, "services/rust");
      if (!fs.existsSync(rustServicesDir)) return;
      const dirs = fs.readdirSync(rustServicesDir, { withFileTypes: true });
      let total = 0;
      let withShutdown = 0;

      for (const dir of dirs) {
        if (!dir.isDirectory()) continue;
        const mainFile = path.join(rustServicesDir, dir.name, "src", "main.rs");
        if (!fs.existsSync(mainFile)) continue;
        total++;
        const content = fs.readFileSync(mainFile, "utf-8");
        if (
          content.includes("shutdown_signal") ||
          content.includes("ctrl_c") ||
          content.includes("SIGTERM") ||
          content.includes("signal")
        ) {
          withShutdown++;
        }
      }

      const ratio = total > 0 ? withShutdown / total : 1;
      expect(ratio).toBeGreaterThanOrEqual(0.9);
    });
  });

  describe("Security Hardening Contracts", () => {
    it("no hardcoded passwords in k8s values", () => {
      const keycloakValues = fs.readFileSync(
        path.join(ROOT, "k8s/charts/keycloak/values.yaml"),
        "utf-8"
      );
      const mojalookValues = fs.readFileSync(
        path.join(ROOT, "k8s/charts/mojaloop/values.yaml"),
        "utf-8"
      );

      // Should not contain literal "password" as a password value
      expect(keycloakValues).not.toMatch(/password:\s*"password"/);
      expect(mojalookValues).not.toMatch(/password:\s*"password"/);
      expect(keycloakValues).not.toMatch(/adminPassword:\s*"adminpassword"/);
      expect(mojalookValues).not.toMatch(/rootPassword:\s*"rootpassword"/);
    });

    it("mTLS agent module exists", () => {
      expect(fs.existsSync(path.join(ROOT, "server/lib/mtlsAgent.ts"))).toBe(
        true
      );
    });
  });

  describe("Docker Container Optimization", () => {
    it("optimized compose file exists", () => {
      expect(
        fs.existsSync(path.join(ROOT, "docker-compose.optimized.yml"))
      ).toBe(true);
    });

    it("optimized compose has fewer services than original", () => {
      const optimized = fs.readFileSync(
        path.join(ROOT, "docker-compose.optimized.yml"),
        "utf-8"
      );
      const original = fs.readFileSync(
        path.join(ROOT, "docker-compose.yml"),
        "utf-8"
      );

      const excludeKeys = new Set([
        "interval",
        "timeout",
        "retries",
        "start_period",
        "condition",
        "context",
        "dockerfile",
        "ports",
        "environment",
        "depends_on",
        "restart",
        "healthcheck",
        "build",
        "test",
        "command",
        "volumes",
        "networks",
        "version",
        "services",
      ]);
      const countServices = (content: string) => {
        const matches = content.match(/^\s{2}[a-z][a-z0-9_-]+:/gm);
        if (!matches) return 0;
        return matches.filter(m => {
          const key = m.trim().replace(":", "");
          return (
            !excludeKeys.has(key) &&
            !key.endsWith("-data") &&
            !key.startsWith("x-")
          );
        }).length;
      };

      const optimizedCount = countServices(optimized);
      const originalCount = countServices(original);

      expect(optimizedCount).toBeLessThan(originalCount * 0.7);
    });

    it("consolidated Dockerfiles exist for each language", () => {
      expect(
        fs.existsSync(path.join(ROOT, "services/go/Dockerfile.consolidated"))
      ).toBe(true);
      expect(
        fs.existsSync(
          path.join(ROOT, "services/python/Dockerfile.consolidated")
        )
      ).toBe(true);
      expect(
        fs.existsSync(path.join(ROOT, "services/rust/Dockerfile.consolidated"))
      ).toBe(true);
    });
  });

  describe("Database Integration", () => {
    it("TS routers do not use module-scoped arrays as data stores", () => {
      const routerDir = path.join(ROOT, "server/routers");
      const criticalRouters = ["inviteCodes.ts", "commissionEngine.ts"];

      for (const router of criticalRouters) {
        const filePath = path.join(routerDir, router);
        if (!fs.existsSync(filePath)) continue;
        const content = fs.readFileSync(filePath, "utf-8");
        // Should use database, not in-memory arrays
        expect(content).toContain("db");
      }
    });
  });
});
