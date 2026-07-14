// Production graceful degradation — wraps all routers with fallback behavior
import { TRPCError } from "@trpc/server";

interface DegradationConfig {
  enabled: boolean;
  maxResponseTimeMs: number;
  fallbackEnabled: boolean;
  readOnlyMode: boolean;
}

const degradationConfig: DegradationConfig = {
  enabled: process.env.DEGRADATION_ENABLED === "true",
  maxResponseTimeMs: parseInt(process.env.DEGRADATION_TIMEOUT_MS || "15000"),
  fallbackEnabled: process.env.DEGRADATION_FALLBACK === "true",
  readOnlyMode: process.env.READ_ONLY_MODE === "true",
};

const serviceHealth = new Map<
  string,
  { healthy: boolean; lastCheck: number; consecutiveFailures: number }
>();

export function checkServiceHealth(service: string): boolean {
  const state = serviceHealth.get(service);
  if (!state) return true;
  if (Date.now() - state.lastCheck > 60_000) return true; // stale, assume healthy
  return state.healthy;
}

export function reportServiceHealth(service: string, healthy: boolean) {
  const current = serviceHealth.get(service) || {
    healthy: true,
    lastCheck: 0,
    consecutiveFailures: 0,
  };
  current.lastCheck = Date.now();
  if (healthy) {
    current.healthy = true;
    current.consecutiveFailures = 0;
  } else {
    current.consecutiveFailures++;
    current.healthy = current.consecutiveFailures < 3;
  }
  serviceHealth.set(service, current);
}

export function isDegradedMode(): boolean {
  return degradationConfig.enabled || degradationConfig.readOnlyMode;
}

export function isReadOnlyMode(): boolean {
  return degradationConfig.readOnlyMode;
}

export function getDegradationStatus(): {
  mode: string;
  services: Record<string, { healthy: boolean; consecutiveFailures: number }>;
} {
  const services: Record<
    string,
    { healthy: boolean; consecutiveFailures: number }
  > = {};
  serviceHealth.forEach((v, k) => {
    services[k] = {
      healthy: v.healthy,
      consecutiveFailures: v.consecutiveFailures,
    };
  });
  return {
    mode: degradationConfig.readOnlyMode
      ? "read-only"
      : degradationConfig.enabled
        ? "degraded"
        : "normal",
    services,
  };
}

export async function withDegradation<T>(
  service: string,
  operation: () => Promise<T>,
  fallback?: () => T
): Promise<T> {
  try {
    const result = await Promise.race([
      operation(),
      new Promise<never>((_, reject) =>
        setTimeout(
          () => reject(new Error(`${service} timed out`)),
          degradationConfig.maxResponseTimeMs
        )
      ),
    ]);
    reportServiceHealth(service, true);
    return result;
  } catch (error) {
    reportServiceHealth(service, false);
    if (fallback && degradationConfig.fallbackEnabled) {
      return fallback();
    }
    throw error;
  }
}
