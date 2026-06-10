/**
 * Circuit Breaker — protects external service calls with automatic fallback.
 *
 * States:
 *   CLOSED  → normal operation, requests pass through
 *   OPEN    → service is down, requests fail fast or use fallback
 *   HALF_OPEN → testing if service recovered (limited requests)
 *
 * Integrates with productionDegradation for platform-wide health tracking.
 */

import {
  reportServiceHealth,
  checkServiceHealth,
} from "../middleware/productionDegradation";

type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";

interface CircuitBreakerOptions {
  failureThreshold: number;
  resetTimeoutMs: number;
  halfOpenMaxAttempts: number;
  timeoutMs: number;
}

interface CircuitStats {
  state: CircuitState;
  failures: number;
  successes: number;
  lastFailure: number | null;
  lastSuccess: number | null;
  totalRequests: number;
  totalFailures: number;
}

const DEFAULT_OPTIONS: CircuitBreakerOptions = {
  failureThreshold: 5,
  resetTimeoutMs: 30_000,
  halfOpenMaxAttempts: 3,
  timeoutMs: 10_000,
};

const breakers = new Map<
  string,
  { state: CircuitState; stats: CircuitStats; options: CircuitBreakerOptions }
>();

function getBreaker(name: string, options?: Partial<CircuitBreakerOptions>) {
  let breaker = breakers.get(name);
  if (!breaker) {
    breaker = {
      state: "CLOSED",
      stats: {
        state: "CLOSED",
        failures: 0,
        successes: 0,
        lastFailure: null,
        lastSuccess: null,
        totalRequests: 0,
        totalFailures: 0,
      },
      options: { ...DEFAULT_OPTIONS, ...options },
    };
    breakers.set(name, breaker);
  }
  return breaker;
}

/**
 * Execute a function with circuit breaker protection.
 * If the circuit is open, the fallback is returned immediately.
 * If no fallback is provided, throws an error.
 */
export async function withCircuitBreaker<T>(
  serviceName: string,
  fn: () => Promise<T>,
  fallback?: () => T | Promise<T>,
  options?: Partial<CircuitBreakerOptions>
): Promise<T> {
  const breaker = getBreaker(serviceName, options);
  breaker.stats.totalRequests++;

  if (breaker.state === "OPEN") {
    const elapsed = Date.now() - (breaker.stats.lastFailure ?? 0);
    if (elapsed > breaker.options.resetTimeoutMs) {
      breaker.state = "HALF_OPEN";
      breaker.stats.state = "HALF_OPEN";
    } else {
      if (fallback) return fallback();
      throw new Error(
        `Circuit breaker OPEN for ${serviceName} — service unavailable`
      );
    }
  }

  try {
    const result = await Promise.race([
      fn(),
      new Promise<never>((_, reject) =>
        setTimeout(
          () => reject(new Error(`Timeout: ${serviceName}`)),
          breaker.options.timeoutMs
        )
      ),
    ]);

    breaker.stats.successes++;
    breaker.stats.lastSuccess = Date.now();
    breaker.stats.failures = 0;

    if (breaker.state === "HALF_OPEN") {
      breaker.state = "CLOSED";
      breaker.stats.state = "CLOSED";
    }

    reportServiceHealth(serviceName, true);
    return result;
  } catch (err) {
    breaker.stats.failures++;
    breaker.stats.totalFailures++;
    breaker.stats.lastFailure = Date.now();

    if (breaker.stats.failures >= breaker.options.failureThreshold) {
      breaker.state = "OPEN";
      breaker.stats.state = "OPEN";
    }

    reportServiceHealth(serviceName, false);

    if (fallback) return fallback();
    throw err;
  }
}

/**
 * Execute a function with automatic retry and exponential backoff.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options?: { maxRetries?: number; baseDelayMs?: number; maxDelayMs?: number }
): Promise<T> {
  const maxRetries = options?.maxRetries ?? 3;
  const baseDelay = options?.baseDelayMs ?? 1000;
  const maxDelay = options?.maxDelayMs ?? 10000;

  let lastError: Error | undefined;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < maxRetries) {
        const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
        const jitter =
          delay *
          (0.5 +
            (crypto.getRandomValues(new Uint32Array(1))[0] / 4294967295) * 0.5);
        await new Promise(resolve => setTimeout(resolve, jitter));
      }
    }
  }

  throw lastError;
}

/**
 * Get circuit breaker stats for monitoring.
 */
export function getCircuitBreakerStats(): Record<string, CircuitStats> {
  const result: Record<string, CircuitStats> = {};
  for (const [name, breaker] of breakers) {
    result[name] = { ...breaker.stats, state: breaker.state };
  }
  return result;
}

/**
 * Reset a specific circuit breaker (for manual recovery).
 */
export function resetCircuitBreaker(serviceName: string): void {
  const breaker = breakers.get(serviceName);
  if (breaker) {
    breaker.state = "CLOSED";
    breaker.stats.failures = 0;
    breaker.stats.state = "CLOSED";
    reportServiceHealth(serviceName, true);
  }
}
