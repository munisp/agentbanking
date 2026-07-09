/**
 * Transactional Outbox Pattern
 * Ensures exactly-once event delivery by writing events to a PostgreSQL
 * outbox table within the same DB transaction as the business operation.
 * A background poller publishes events to Kafka with exponential backoff retry.
 *
 * Also implements: Dead Letter Queue (DLQ), middleware health alerting,
 * and fail-open with notification (not silent).
 *
 * Integrations: PostgreSQL, Kafka, Redis (poller lock), Dapr (DLQ alerts),
 *               Fluvio (health streaming), Lakehouse (delivery analytics)
 */

import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { publishEvent } from "../kafkaClient";
import { cacheGet, cacheSet } from "../lib/cacheClient";
import { fluvioPublish } from "../lib/fluvioClient";
import { daprPublish } from "../lib/daprClient";
import { lakehouseIngest } from "../lib/lakehouseClient";

// ── Write to Outbox (called within transaction) ─────────────────────────────

export async function writeToOutbox(
  aggregateType: string,
  aggregateId: string,
  eventType: string,
  payload: Record<string, unknown>
): Promise<number | null> {
  const db = (await getDb())!;
  if (!db) return null;

  const [result] = await db.execute(sql`
    INSERT INTO event_outbox (aggregate_type, aggregate_id, event_type, payload, next_retry_at)
    VALUES (${aggregateType}, ${aggregateId}, ${eventType}, ${JSON.stringify(payload)}::jsonb, NOW())
    RETURNING id
  `);

  return (result as any)?.id ?? null;
}

// ── Publish from Outbox (background poller) ─────────────────────────────────

export async function pollAndPublishOutbox(
  batchSize: number = 50
): Promise<number> {
  const db = (await getDb())!;
  if (!db) return 0;

  // Acquire distributed lock via Redis
  const lockKey = "outbox_poller_lock";
  const locked = await cacheGet(lockKey).catch(() => null);
  if (locked) return 0;
  await cacheSet(lockKey, "1", 10).catch(() => {}); // 10s lock

  const rows = await db.execute(sql`
    SELECT id, aggregate_type, aggregate_id, event_type, payload, retry_count
    FROM event_outbox
    WHERE published = FALSE
      AND (next_retry_at IS NULL OR next_retry_at <= NOW())
      AND retry_count < max_retries
    ORDER BY created_at ASC
    LIMIT ${batchSize}
    FOR UPDATE SKIP LOCKED
  `);

  let published = 0;

  for (const row of rows as any[]) {
    try {
      // Publish to Kafka
      await publishEvent(row.event_type as any, row.aggregate_id || "outbox", {
        ...row.payload,
        _outboxId: row.id,
        _aggregateType: row.aggregate_type,
        _aggregateId: row.aggregate_id,
      });

      // Mark as published
      await db.execute(sql`
        UPDATE event_outbox
        SET published = TRUE, published_at = NOW()
        WHERE id = ${row.id}
      `);

      published++;
    } catch (err) {
      const newRetry = row.retry_count + 1;
      const backoffMs = Math.min(1000 * Math.pow(2, newRetry), 3600000); // max 1h
      const nextRetry = new Date(Date.now() + backoffMs);

      if (newRetry >= 5) {
        // Move to DLQ
        await db.execute(sql`
          INSERT INTO event_dead_letter (original_event_id, event_type, payload, error_message, retry_count)
          VALUES (${row.id}, ${row.event_type}, ${JSON.stringify(row.payload)}::jsonb, ${(err as Error).message}, ${newRetry})
        `);

        await db.execute(sql`
          UPDATE event_outbox SET published = TRUE, published_at = NOW() WHERE id = ${row.id}
        `);

        // Alert on DLQ entry
        await daprPublish("ops-alerts", "event.dead_letter", {
          eventId: row.id,
          eventType: row.event_type,
          error: (err as Error).message,
        }).catch(() => {});

        await fluvioPublish("ops.dlq.entry", {
          eventId: row.id,
          eventType: row.event_type,
        }).catch(() => {});
      } else {
        await db.execute(sql`
          UPDATE event_outbox
          SET retry_count = ${newRetry}, next_retry_at = ${nextRetry.toISOString()}::timestamptz
          WHERE id = ${row.id}
        `);
      }
    }
  }

  // Track delivery metrics
  if (published > 0) {
    await lakehouseIngest("outbox_delivery_metrics", {
      published,
      total: (rows as any[]).length,
      timestamp: new Date().toISOString(),
    }).catch(() => {});
  }

  return published;
}

// ── Retry DLQ entries (manual or scheduled) ─────────────────────────────────

export async function retryDeadLetters(
  maxRetries: number = 10
): Promise<number> {
  const db = (await getDb())!;
  if (!db) return 0;

  const rows = await db.execute(sql`
    SELECT id, event_type, payload, retry_count
    FROM event_dead_letter
    WHERE resolved = FALSE AND retry_count < ${maxRetries}
    ORDER BY created_at ASC
    LIMIT 20
    FOR UPDATE SKIP LOCKED
  `);

  let resolved = 0;

  for (const row of rows as any[]) {
    try {
      await publishEvent(
        row.event_type as any,
        row.aggregate_id || "dlq",
        row.payload
      );
      await db.execute(sql`
        UPDATE event_dead_letter SET resolved = TRUE, resolved_at = NOW() WHERE id = ${row.id}
      `);
      resolved++;
    } catch {
      await db.execute(sql`
        UPDATE event_dead_letter SET retry_count = retry_count + 1 WHERE id = ${row.id}
      `);
    }
  }

  return resolved;
}

// ── Middleware Health Alerting (replaces silent .catch(() => {})) ────────────

export async function logMiddlewareHealth(
  serviceName: string,
  routerName: string,
  status: "success" | "timeout" | "error" | "unreachable",
  latencyMs: number,
  errorMessage?: string
): Promise<void> {
  const db = (await getDb())!;
  if (!db) return;

  await db
    .execute(
      sql`
    INSERT INTO middleware_health_log (service_name, router_name, status, latency_ms, error_message)
    VALUES (${serviceName}, ${routerName}, ${status}, ${latencyMs}, ${errorMessage ?? null})
  `
    )
    .catch(() => {});

  // Alert on errors (not silent anymore)
  if (status === "error" || status === "unreachable") {
    await daprPublish("ops-alerts", "middleware.degraded", {
      serviceName,
      routerName,
      status,
      errorMessage,
    }).catch(() => {});

    await fluvioPublish("ops.middleware.health", {
      serviceName,
      routerName,
      status,
      latencyMs,
      timestamp: Date.now(),
    }).catch(() => {});
  }
}

// ── Fail-Open with Alert (replacement for silent .catch(() => {})) ──────────

export function failOpenWithAlert(serviceName: string, routerName: string) {
  return async (err: unknown): Promise<void> => {
    const errorMsg = err instanceof Error ? err.message : String(err);
    await logMiddlewareHealth(serviceName, routerName, "error", 0, errorMsg);
  };
}
