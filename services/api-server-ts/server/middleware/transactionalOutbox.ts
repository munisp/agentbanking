/**
 * Transactional Outbox Pattern (port of root server/middleware/transactionalOutbox.ts)
 * ─────────────────────────────────────────────────────────────────────────────
 * Ensures exactly-once event delivery by writing events to the PostgreSQL
 * `outbox_events` table within the SAME DB transaction as the business
 * operation (use writeToOutboxTx inside withTransaction). A background poller
 * publishes pending events to Kafka with bounded exponential-backoff retry;
 * events that exhaust their retries are moved to `outbox_dead_letters` so
 * nothing is ever silently dropped.
 *
 * Schema: migrations/0058_outbox_events.sql
 */

import { getDb } from "../db";
import { sql } from "drizzle-orm";
import { publishEvent } from "../kafkaClient";

// ── Write to Outbox ───────────────────────────────────────────────────────────

/**
 * Write an event to the outbox INSIDE an existing transaction.
 * Call with the `tx` handle provided by withTransaction so the event row
 * commits or rolls back atomically with the business operation:
 *
 *   await withTransaction(async (tx) => {
 *     ...business writes...
 *     await writeToOutboxTx(tx, "agent", agentId, "pos.agents.registered", {...});
 *   });
 */
export async function writeToOutboxTx(
  tx: any,
  aggregateType: string,
  aggregateId: string,
  eventType: string,
  payload: Record<string, unknown>
): Promise<number | null> {
  const [result] = await tx.execute(sql`
    INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload, next_retry_at)
    VALUES (${aggregateType}, ${aggregateId}, ${eventType}, ${JSON.stringify(payload)}::jsonb, NOW())
    RETURNING id
  `);

  return (result as any)?.id ?? null;
}

/**
 * Write an event to the outbox outside a transaction (standalone).
 * Prefer writeToOutboxTx inside withTransaction whenever the event
 * accompanies a business write.
 */
export async function writeToOutbox(
  aggregateType: string,
  aggregateId: string,
  eventType: string,
  payload: Record<string, unknown>
): Promise<number | null> {
  const db = await getDb();
  if (!db) return null;
  return writeToOutboxTx(db, aggregateType, aggregateId, eventType, payload);
}

// ── Publish from Outbox (background poller) ───────────────────────────────────

/**
 * Poll unpublished outbox events and publish them to Kafka.
 * On publish failure the event is retried with exponential backoff
 * (2^retry_count seconds, capped at 1h); once retry_count reaches max_retries
 * the event is moved to outbox_dead_letters instead of being dropped.
 */
export async function pollAndPublishOutbox(
  batchSize: number = 50
): Promise<number> {
  const db = await getDb();
  if (!db) return 0;

  const rows = await db.execute(sql`
    SELECT id, aggregate_type, aggregate_id, event_type, payload, retry_count
    FROM outbox_events
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
      // Publish to Kafka (publishEvent is fail-open — returns false after
      // its internal retries/DLQ attempt, so treat false as failure here)
      const ok = await publishEvent(row.event_type as any, row.aggregate_id || "outbox", {
        ...row.payload,
        _outboxId: row.id,
        _aggregateType: row.aggregate_type,
        _aggregateId: row.aggregate_id,
      });
      if (!ok) throw new Error("Kafka publish failed after retries");

      // Mark as published
      await db.execute(sql`
        UPDATE outbox_events
        SET published = TRUE, published_at = NOW()
        WHERE id = ${row.id}
      `);

      published++;
    } catch (err) {
      const newRetry = row.retry_count + 1;
      const backoffMs = Math.min(1000 * Math.pow(2, newRetry), 3600000); // max 1h
      const nextRetry = new Date(Date.now() + backoffMs);

      if (newRetry >= 5) {
        // Move to dead letters — never silently drop
        await db.execute(sql`
          INSERT INTO outbox_dead_letters (original_event_id, event_type, payload, error_message, retry_count)
          VALUES (${row.id}, ${row.event_type}, ${JSON.stringify(row.payload)}::jsonb, ${(err as Error).message}, ${newRetry})
        `);

        await db.execute(sql`
          UPDATE outbox_events SET published = TRUE, published_at = NOW() WHERE id = ${row.id}
        `);

        console.error(
          `[Outbox] Event ${row.id} (${row.event_type}) dead-lettered after ${newRetry} attempts:`,
          (err as Error).message
        );
      } else {
        await db.execute(sql`
          UPDATE outbox_events
          SET retry_count = ${newRetry}, next_retry_at = ${nextRetry.toISOString()}::timestamptz
          WHERE id = ${row.id}
        `);
      }
    }
  }

  return published;
}

// ── Retry dead letters (manual or scheduled) ──────────────────────────────────

export async function retryDeadLetters(
  maxRetries: number = 10
): Promise<number> {
  const db = await getDb();
  if (!db) return 0;

  const rows = await db.execute(sql`
    SELECT id, event_type, payload, retry_count
    FROM outbox_dead_letters
    WHERE resolved = FALSE AND retry_count < ${maxRetries}
    ORDER BY created_at ASC
    LIMIT 20
    FOR UPDATE SKIP LOCKED
  `);

  let resolved = 0;

  for (const row of rows as any[]) {
    try {
      const ok = await publishEvent(row.event_type as any, "dlq", row.payload);
      if (!ok) throw new Error("Kafka publish failed after retries");
      await db.execute(sql`
        UPDATE outbox_dead_letters SET resolved = TRUE, resolved_at = NOW() WHERE id = ${row.id}
      `);
      resolved++;
    } catch {
      await db.execute(sql`
        UPDATE outbox_dead_letters SET retry_count = retry_count + 1 WHERE id = ${row.id}
      `);
    }
  }

  return resolved;
}
