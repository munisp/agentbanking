// Production-grade resilient HTTP client with retries, circuit breaker, and timeout
import { TRPCError } from "@trpc/server";
import crypto from "crypto";

interface CircuitBreakerState {
  failures: number;
  lastFailure: number;
  state: "closed" | "open" | "half-open";
}

const circuitBreakers = new Map<string, CircuitBreakerState>();
const CIRCUIT_THRESHOLD = 5;
const CIRCUIT_RESET_MS = 30_000;

function getCircuitState(service: string): CircuitBreakerState {
  if (!circuitBreakers.has(service)) {
    circuitBreakers.set(service, {
      failures: 0,
      lastFailure: 0,
      state: "closed",
    });
  }
  const cb = circuitBreakers.get(service)!;
  if (cb.state === "open" && Date.now() - cb.lastFailure > CIRCUIT_RESET_MS) {
    cb.state = "half-open";
  }
  return cb;
}

function recordSuccess(service: string) {
  const cb = getCircuitState(service);
  cb.failures = 0;
  cb.state = "closed";
}

function recordFailure(service: string) {
  const cb = getCircuitState(service);
  cb.failures++;
  cb.lastFailure = Date.now();
  if (cb.failures >= CIRCUIT_THRESHOLD) {
    cb.state = "open";
  }
}

export async function resilientFetch(
  url: string,
  options: RequestInit & {
    service?: string;
    maxRetries?: number;
    timeoutMs?: number;
    backoffMs?: number;
  } = {}
): Promise<Response> {
  const {
    service = new URL(url).hostname,
    maxRetries = 3,
    timeoutMs = 10_000,
    backoffMs = 500,
    ...fetchOpts
  } = options;

  const cb = getCircuitState(service);
  if (cb.state === "open") {
    throw new TRPCError({
      code: "SERVICE_UNAVAILABLE",
      message: `Circuit breaker open for ${service}`,
    });
  }

  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);

      const response = await fetch(url, {
        ...fetchOpts,
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (response.ok || response.status < 500) {
        recordSuccess(service);
        return response;
      }

      lastError = new Error(`HTTP ${response.status}: ${response.statusText}`);
    } catch (err: unknown) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }

    if (attempt < maxRetries) {
      const delay = backoffMs * Math.pow(2, attempt) + crypto.getRandomValues(new Uint32Array(1))[0] / 4294967295 * 100;
      await new Promise(r => setTimeout(r, delay));
    }
  }

  recordFailure(service);
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${service} failed after ${maxRetries + 1} attempts: ${lastError?.message}`,
  });
}

export function getCircuitBreakerStatus(): Record<string, CircuitBreakerState> {
  const result: Record<string, CircuitBreakerState> = {};
  circuitBreakers.forEach((v, k) => {
    result[k] = { ...v };
  });
  return result;
}
