/**
 * Production Observability — structured logging, distributed tracing, and alerting.
 * Integrates with OpenTelemetry, Prometheus, and webhook-based alert channels.
 */

import { IncomingMessage } from "http";

// --- Structured Logging ---

type LogLevel = "debug" | "info" | "warn" | "error" | "fatal";

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  service: string;
  traceId?: string;
  spanId?: string;
  message: string;
  context?: Record<string, unknown>;
  duration_ms?: number;
}

const SERVICE_NAME = process.env.SERVICE_NAME || "54agent-app";
const LOG_LEVEL: LogLevel = (process.env.LOG_LEVEL as LogLevel) || "info";

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  fatal: 4,
};

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= LOG_LEVELS[LOG_LEVEL];
}

export function structuredLog(
  level: LogLevel,
  message: string,
  context?: Record<string, unknown>
): void {
  if (!shouldLog(level)) return;

  const entry: LogEntry = {
    timestamp: new Date().toISOString(),
    level,
    service: SERVICE_NAME,
    message,
    context,
  };

  const output = JSON.stringify(entry);
  if (level === "error" || level === "fatal") {
    console.error(output);
  } else {
    console.log(output);
  }
}

export const logger = {
  debug: (msg: string, ctx?: Record<string, unknown>) =>
    structuredLog("debug", msg, ctx),
  info: (msg: string, ctx?: Record<string, unknown>) =>
    structuredLog("info", msg, ctx),
  warn: (msg: string, ctx?: Record<string, unknown>) =>
    structuredLog("warn", msg, ctx),
  error: (msg: string, ctx?: Record<string, unknown>) =>
    structuredLog("error", msg, ctx),
  fatal: (msg: string, ctx?: Record<string, unknown>) =>
    structuredLog("fatal", msg, ctx),
};

// --- Distributed Tracing Context ---

export function extractTraceContext(req: IncomingMessage): {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
} {
  const traceparent = req.headers["traceparent"] as string;
  if (traceparent) {
    const parts = traceparent.split("-");
    if (parts.length >= 4) {
      return {
        traceId: parts[1],
        spanId: parts[2],
        parentSpanId: undefined,
      };
    }
  }

  return {
    traceId: generateId(32),
    spanId: generateId(16),
  };
}

function generateId(length: number): string {
  const chars = "0123456789abcdef";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * chars.length)];
  }
  return result;
}

export function createTraceparent(traceId: string, spanId: string): string {
  return `00-${traceId}-${spanId}-01`;
}

// --- Metrics Collection ---

interface MetricPoint {
  name: string;
  value: number;
  labels: Record<string, string>;
  timestamp: number;
}

const metricsBuffer: MetricPoint[] = [];

export function recordMetric(
  name: string,
  value: number,
  labels: Record<string, string> = {}
): void {
  metricsBuffer.push({
    name,
    value,
    labels: { service: SERVICE_NAME, ...labels },
    timestamp: Date.now(),
  });

  // Keep buffer bounded
  if (metricsBuffer.length > 10000) {
    metricsBuffer.splice(0, 5000);
  }
}

export function getMetrics(): MetricPoint[] {
  return [...metricsBuffer];
}

export function getMetricsPrometheus(): string {
  const grouped = new Map<string, MetricPoint[]>();
  for (const m of metricsBuffer) {
    const key = m.name;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(m);
  }

  let output = "";
  for (const [name, points] of grouped) {
    output += `# TYPE ${name} gauge\n`;
    for (const p of points.slice(-100)) {
      const labels = Object.entries(p.labels)
        .map(([k, v]) => `${k}="${v}"`)
        .join(",");
      output += `${name}{${labels}} ${p.value} ${p.timestamp}\n`;
    }
  }
  return output;
}

// --- Alerting ---

type AlertSeverity = "info" | "warning" | "critical" | "fatal";

interface Alert {
  id: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  service: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  acknowledged: boolean;
}

const activeAlerts: Alert[] = [];
const ALERT_WEBHOOK_URL = process.env.ALERT_WEBHOOK_URL;
const ALERT_SLACK_WEBHOOK = process.env.ALERT_SLACK_WEBHOOK;

export async function sendAlert(
  severity: AlertSeverity,
  title: string,
  description: string,
  metadata?: Record<string, unknown>
): Promise<void> {
  const alert: Alert = {
    id: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    severity,
    title,
    description,
    service: SERVICE_NAME,
    timestamp: new Date().toISOString(),
    metadata,
    acknowledged: false,
  };

  activeAlerts.push(alert);
  if (activeAlerts.length > 1000) activeAlerts.splice(0, 500);

  logger.warn(`[ALERT:${severity}] ${title}: ${description}`, metadata);

  // Send to webhook channels
  const payload = JSON.stringify(alert);

  if (ALERT_WEBHOOK_URL) {
    try {
      await fetch(ALERT_WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
    } catch (err) {
      logger.error("Failed to send alert to webhook", {
        error: String(err),
      });
    }
  }

  if (ALERT_SLACK_WEBHOOK) {
    try {
      const slackPayload = {
        text: `🚨 *[${severity.toUpperCase()}]* ${title}\n${description}\nService: ${SERVICE_NAME}`,
        attachments: metadata
          ? [
              {
                fields: Object.entries(metadata).map(([k, v]) => ({
                  title: k,
                  value: String(v),
                  short: true,
                })),
              },
            ]
          : undefined,
      };
      await fetch(ALERT_SLACK_WEBHOOK, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(slackPayload),
      });
    } catch (err) {
      logger.error("Failed to send alert to Slack", {
        error: String(err),
      });
    }
  }
}

export function getActiveAlerts(): Alert[] {
  return activeAlerts.filter(a => !a.acknowledged);
}

export function acknowledgeAlert(alertId: string): boolean {
  const alert = activeAlerts.find(a => a.id === alertId);
  if (alert) {
    alert.acknowledged = true;
    return true;
  }
  return false;
}

// --- Request Timing Middleware Helper ---

export function requestTimer(): {
  start: () => void;
  end: (labels?: Record<string, string>) => number;
} {
  let startTime = 0;
  return {
    start() {
      startTime = performance.now();
    },
    end(labels = {}) {
      const duration = performance.now() - startTime;
      recordMetric("http_request_duration_ms", duration, labels);
      return duration;
    },
  };
}

// --- Engine Metrics (used by loadTestMetrics router) ---

interface EngineMetrics {
  totalOperations: number;
  successCount: number;
  errorCount: number;
  totalDurationMs: number;
  avgDurationMs: number;
}

const engineMetricsMap = new Map<string, EngineMetrics>();

export function getAllEngineMetrics(): Record<string, EngineMetrics> {
  const result: Record<string, EngineMetrics> = {};
  engineMetricsMap.forEach((v, k) => {
    result[k] = { ...v };
  });
  return result;
}

export function exportPrometheusMetrics(): string {
  let output = "";
  for (const [engine, metrics] of engineMetricsMap) {
    const prefix = `fiveforlink_${engine}`;
    output += `# TYPE ${prefix}_operations_total counter\n`;
    output += `${prefix}_operations_total ${metrics.totalOperations}\n`;
    output += `# TYPE ${prefix}_success_total counter\n`;
    output += `${prefix}_success_total ${metrics.successCount}\n`;
    output += `# TYPE ${prefix}_error_total counter\n`;
    output += `${prefix}_error_total ${metrics.errorCount}\n`;
    output += `# TYPE ${prefix}_duration_ms gauge\n`;
    output += `${prefix}_duration_ms ${metrics.avgDurationMs.toFixed(2)}\n`;
  }
  if (output === "") {
    output = getMetricsPrometheus();
  }
  return output;
}

// --- Span Tracking (used by sprint58 and p0p3 tests and request tracing) ---

interface SpanEvent {
  name: string;
  timestamp: number;
  attributes: Record<string, unknown>;
}

interface SpanContext {
  spanId: string;
  traceId: string;
  engine: string;
  operationName: string;
  serviceName: string;
  attributes: Record<string, unknown>;
  startTime: number;
  endTime?: number;
  status: string;
  duration_ms?: number;
  events: SpanEvent[];
}

const activeSpans = new Map<string, SpanContext>();
const completedSpans: SpanContext[] = [];

export function startSpan(
  engine: string,
  operation: string,
  attrs?: Record<string, unknown>
): SpanContext {
  const span: SpanContext = {
    spanId: generateId(16),
    traceId: generateId(32),
    engine,
    operationName: operation,
    serviceName: `54agent.${engine}`,
    attributes: { engine, ...attrs },
    startTime: performance.now(),
    status: "unset",
    events: [],
  };
  activeSpans.set(span.spanId, span);
  return span;
}

export function addSpanEvent(
  spanId: string,
  name: string,
  attributes: Record<string, unknown> = {}
): void {
  const span = activeSpans.get(spanId);
  if (!span) return;
  span.events.push({ name, timestamp: performance.now(), attributes });
}

export function endSpan(
  spanId: string,
  status?: string,
  errorMessage?: string
): SpanContext | null {
  const span = activeSpans.get(spanId);
  if (!span) return null;
  span.endTime = performance.now();
  span.status = status || "ok";
  span.duration_ms = span.endTime - span.startTime;
  if (errorMessage) {
    span.attributes["error.message"] = errorMessage;
  }
  activeSpans.delete(spanId);
  completedSpans.push(span);

  // Update engine metrics
  const engine = span.engine;
  if (!engineMetricsMap.has(engine)) {
    engineMetricsMap.set(engine, {
      totalOperations: 0,
      successCount: 0,
      errorCount: 0,
      totalDurationMs: 0,
      avgDurationMs: 0,
    });
  }
  const em = engineMetricsMap.get(engine)!;
  em.totalOperations++;
  if (span.status === "error") {
    em.errorCount++;
  } else {
    em.successCount++;
  }
  em.totalDurationMs += span.duration_ms;
  em.avgDurationMs = em.totalDurationMs / em.totalOperations;

  recordMetric("span_duration_ms", span.duration_ms, {
    engine: span.engine,
    operation: span.operationName,
    status: span.status,
  });
  return span;
}

export function getEngineMetrics(engine: string): EngineMetrics | null {
  return engineMetricsMap.get(engine) || null;
}

export function getActiveSpans(): SpanContext[] {
  return Array.from(activeSpans.values());
}

export function resetMetrics(): void {
  metricsBuffer.length = 0;
  activeSpans.clear();
  completedSpans.length = 0;
  engineMetricsMap.clear();
}

export function getMetricsSummary(): {
  totalSpans: number;
  activeSpans: number;
  metricsCount: number;
} {
  return {
    totalSpans: completedSpans.length,
    activeSpans: activeSpans.size,
    metricsCount: metricsBuffer.length,
  };
}

// --- Engine Tracers ---

interface EngineTracer {
  withSpan: <T>(
    operation: string,
    fn: (span: SpanContext) => Promise<T>
  ) => Promise<T>;
}

function createEngineTracer(engine: string): EngineTracer {
  return {
    async withSpan<T>(
      operation: string,
      fn: (span: SpanContext) => Promise<T>
    ): Promise<T> {
      const span = startSpan(engine, operation);
      try {
        const result = await fn(span);
        endSpan(span.spanId, "ok");
        return result;
      } catch (err) {
        endSpan(
          span.spanId,
          "error",
          err instanceof Error ? err.message : String(err)
        );
        throw err;
      }
    },
  };
}

export const settlementTracer = createEngineTracer("settlement");
export const disputeTracer = createEngineTracer("dispute");
export const commissionTracer = createEngineTracer("commission");
export const fraudTracer = createEngineTracer("fraud");
export const kycTracer = createEngineTracer("kyc");

export async function withSpan<T>(
  engine: string,
  operation: string,
  fn: (span: SpanContext) => Promise<T>
): Promise<T> {
  return createEngineTracer(engine).withSpan(operation, fn);
}
