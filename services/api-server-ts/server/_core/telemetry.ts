/**
 * telemetry.ts — OpenTelemetry distributed tracing for 54agent POS Shell
 *
 * Instruments:
 *  - HTTP requests (Express)
 *  - Database queries (pg / drizzle)
 *  - tRPC procedures (via HTTP instrumentation)
 *
 * IMPORTANT: this module must be statically imported FIRST in the server
 * entry point (server/_core/index.ts) so that auto-instrumentation hooks
 * are installed before express / pg / etc. are loaded.
 *
 * Activated only when OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise
 * initTelemetry() is a no-op that logs a single line.
 * Exports traces to an OTLP-compatible collector (Jaeger, Tempo, etc.)
 *
 * Environment variables:
 *  - OTEL_EXPORTER_OTLP_ENDPOINT  e.g. http://jaeger:4318
 *  - OTEL_SERVICE_NAME             defaults to "pos-shell"
 *  - OTEL_SERVICE_VERSION          defaults to package version / "0.0.0"
 *  - ENVIRONMENT / NODE_ENV        deployment.environment.name (default "development")
 */

import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
} from "@opentelemetry/semantic-conventions";
import {
  CompositePropagator,
  W3CBaggagePropagator,
  W3CTraceContextPropagator,
} from "@opentelemetry/core";
import { trace, type Tracer } from "@opentelemetry/api";

// deployment.environment.name is only exported via the incubating semconv
// subpath at 1.40.x; pin the key literally to avoid the extra import surface.
const ATTR_DEPLOYMENT_ENVIRONMENT_NAME = "deployment.environment.name";

/**
 * getTracer returns a named tracer from the global tracer provider.
 * Safe to call before/without SDK initialisation (returns a no-op tracer
 * until a real provider is registered).
 */
export function getTracer(name: string): Tracer {
  return trace.getTracer(name);
}

/**
 * initTelemetry starts the OpenTelemetry NodeSDK when
 * OTEL_EXPORTER_OTLP_ENDPOINT is configured; otherwise it is a no-op.
 */
export function initTelemetry(): void {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;

  if (!endpoint) {
    console.warn(
      "[OTel] OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled (no-op)."
    );
    return;
  }

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME ?? "pos-shell",
      [ATTR_SERVICE_VERSION]:
        process.env.OTEL_SERVICE_VERSION ??
        process.env.npm_package_version ??
        "0.0.0",
      [ATTR_DEPLOYMENT_ENVIRONMENT_NAME]:
        process.env.ENVIRONMENT ?? process.env.NODE_ENV ?? "development",
    }),
    traceExporter: new OTLPTraceExporter({
      url: `${endpoint}/v1/traces`,
    }),
    // W3C TraceContext + Baggage propagation (cross-language contract with
    // the Go services, which use propagation.TraceContext{} + Baggage{}).
    textMapPropagator: new CompositePropagator({
      propagators: [new W3CTraceContextPropagator(), new W3CBaggagePropagator()],
    }),
    instrumentations: [
      getNodeAutoInstrumentations({
        // Reduce noise from internal file system operations
        "@opentelemetry/instrumentation-fs": { enabled: false },
      }),
    ],
  });

  sdk.start();
  console.log(`[OTel] Tracing initialised → ${endpoint}`);

  process.on("SIGTERM", () => {
    sdk.shutdown().catch(err => console.error("[OTel] Shutdown error:", err));
  });
}

// Self-gating side effect: importing this module initialises telemetry when
// configured, and logs one line otherwise.
initTelemetry();
