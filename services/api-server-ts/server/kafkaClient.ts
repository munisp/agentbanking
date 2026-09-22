// TypeScript enabled — Sprint 96 security audit
/**
 * kafkaClient.ts — Kafka integration for 54agent POS Shell
 * ─────────────────────────────────────────────────────────────────────────────
 * Provides a thin wrapper for publishing domain events to Kafka topics.
 * Two modes:
 *
 *  1. Direct KafkaJS (when KAFKA_BROKERS is set) — used in local Docker Compose
 *     and staging environments where the POS Shell has direct broker access.
 *
 *  2. Platform proxy (when only PLATFORM_BASE_URL is available) — forwards
 *     publish calls to the Go event-bus service via APISix gateway.
 *     This is the default in production where the POS Shell sits behind the
 *     gateway and does not have direct broker access.
 *
 * Batching (round-8 perf): publishEvent() calls are accumulated for up to
 * BATCH_LINGER_MS (50ms) or BATCH_MAX_MESSAGES (100) and flushed as a single
 * producer.send({ topicMessages }) with GZIP compression. On a batch-level
 * failure each message falls back to the legacy per-message path, so the
 * round-7 retry/DLQ semantics below are preserved exactly for poison
 * messages. The producer is created with idempotent: true (acks=all,
 * maxInFlight<=5) as supported by kafkajs.
 *
 * Delivery guarantees (mirrors services/shared/kafka_consumer.py DLQ
 * semantics — never silently drop a message):
 *  1. publishEvent() retries the publish with bounded exponential backoff
 *     (PUBLISH_MAX_ATTEMPTS, 250ms base, doubling, capped at 5s).
 *  2. On final failure the event is published to the dead-letter topic
 *     "<topic>.dlq" with an envelope recording the original topic, key,
 *     timestamp, error and attempt count.
 *  3. publishEvent() returns false ONLY after the DLQ attempt; the failure
 *     is always logged with full context so operations can replay the DLQ.
 *
 * Environment variables:
 *  - KAFKA_BROKERS        Comma-separated list e.g. kafka:9092,kafka2:9092
 *  - KAFKA_CLIENT_ID      Defaults to "pos-shell"
 *  - KAFKA_GROUP_ID       Consumer group ID, defaults to "pos-shell-group"
 *  - PLATFORM_BASE_URL    APISix gateway base URL (proxy mode fallback)
 *  - PLATFORM_API_KEY     Bearer token for the gateway
 */

// Default: local Kafka broker from docker-compose.production.yml
const KAFKA_BROKERS = process.env.KAFKA_BROKERS ?? "localhost:9092";
const KAFKA_CLIENT_ID = ENV.kafkaClientId;
const PLATFORM_BASE_URL = ENV.platformBaseUrl;
const PLATFORM_API_KEY = ENV.platformApiKey;

// ── KafkaJS producer (optional direct mode) ───────────────────────────────────
import type { Kafka as KafkaType, Producer, CompressionTypes as CompressionTypesType } from "kafkajs";
import { ENV } from "./_core/env";
let _kafka: KafkaType | null = null;
let _producer: Producer | null = null;
// Cold-start race guard: concurrent first publishers share ONE connect attempt.
let _producerPromise: Promise<Producer | null> | null = null;
// CompressionTypes enum captured from the dynamic kafkajs import (GZIP on send).
let _compressionTypes: typeof CompressionTypesType | null = null;

async function connectProducer(): Promise<Producer | null> {
  try {
    const kafkajs = await import("kafkajs");
    _compressionTypes = kafkajs.CompressionTypes;
    _kafka = new kafkajs.Kafka({
      clientId: KAFKA_CLIENT_ID,
      brokers: KAFKA_BROKERS.split(",").map(b => b.trim()),
      retry: { retries: 3 },
    });
    // idempotent producer: exactly-once per partition, acks=all — supported by
    // kafkajs >= 1.4. allowAutoTopicCreation stays false (topics are provisioned
    // by infra/kafka/create-topics.sh; auto-creation caused per-request backoff
    // storms for ad-hoc topic names before round-8).
    _producer = _kafka.producer({
      allowAutoTopicCreation: false,
      idempotent: true,
    });
    await _producer.connect();
    console.log("[Kafka] Producer connected →", KAFKA_BROKERS);
    return _producer;
  } catch (err) {
    console.warn("[Kafka] Could not connect producer:", (err as Error).message);
    _producer = null;
    return null;
  } finally {
    _producerPromise = null;
  }
}

async function getProducer(): Promise<Producer | null> {
  if (_producer) return _producer;
  if (!_producerPromise) _producerPromise = connectProducer();
  return _producerPromise;
}

// ── Proxy helper ──────────────────────────────────────────────────────────────
async function proxyPublish(
  topic: string,
  key: string,
  payload: unknown
): Promise<void> {
  const res = await fetch(`${PLATFORM_BASE_URL}/v1/events/publish`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${PLATFORM_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ topic, key, payload }),
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) throw new Error(`Kafka proxy publish → ${res.status}`);
}

// ── Domain event types ────────────────────────────────────────────────────────

export type KafkaTopic =
  | "pos.transactions.created"
  | "pos.transactions.reversed"
  | "pos.float.topped_up"
  | "pos.float.depleted"
  | "pos.agents.registered"
  | "pos.agents.suspended"
  | "pos.kyc.submitted"
  | "pos.kyc.approved"
  | "pos.kyc.rejected"
  | "pos.disputes.opened"
  | "pos.disputes.resolved"
  | "pos.fraud.alert_raised"
  // Round-8: single shared topic for tRPC observability events (was ad-hoc
  // per-procedure topics, which failed against allowAutoTopicCreation:false and
  // churned 4× backoff + DLQ per request). "pos.audit.trail" is an existing
  // topic consumed by kafka-event-consumer.ts's default config.
  | "pos.audit.trail";

export interface KafkaEvent<T = unknown> {
  eventId: string;
  eventType: KafkaTopic;
  timestamp: string; // ISO 8601
  agentCode?: string;
  tenantId?: string;
  payload: T;
}

// ── Retry / DLQ configuration ─────────────────────────────────────────────────
// Bounded retry with exponential backoff, then dead-letter on final failure —
// mirrors services/shared/kafka_consumer.py ("<topic>.dlq" suffix, envelope
// with original topic/key/timestamp/error). Messages are never silently dropped.
const PUBLISH_MAX_ATTEMPTS = 4;
const PUBLISH_BACKOFF_BASE_MS = 250;
const PUBLISH_BACKOFF_CAP_MS = 5000;
const DLQ_TOPIC_SUFFIX = ".dlq";

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function publishBackoffMs(attempt: number): number {
  // attempt is 1-based for the retry about to happen
  return Math.min(
    PUBLISH_BACKOFF_BASE_MS * Math.pow(2, attempt - 1),
    PUBLISH_BACKOFF_CAP_MS
  );
}

/**
 * Publish a poison event to the dead-letter topic "<topic>.dlq".
 * Tries the direct producer first, then the platform proxy. Returns true when
 * the event was durably dead-lettered; false only if every DLQ path failed.
 */
async function publishToDeadLetter<T>(
  topic: KafkaTopic,
  key: string,
  event: KafkaEvent<T>,
  error: Error,
  attempts: number
): Promise<boolean> {
  const dlqTopic = `${topic}${DLQ_TOPIC_SUFFIX}`;
  const envelope = {
    original_topic: topic,
    original_key: key,
    failed_at: new Date().toISOString(),
    error: error.message,
    attempts,
    payload: event,
  };
  try {
    const producer = await getProducer();
    if (producer) {
      await producer.send({
        topic: dlqTopic,
        messages: [{ key, value: JSON.stringify(envelope) }],
        compression: _compressionTypes?.GZIP,
      });
      console.warn(`[Kafka] Event dead-lettered → ${dlqTopic} (key=${key})`);
      return true;
    }
    await proxyPublish(dlqTopic, key, envelope);
    console.warn(`[Kafka] Event dead-lettered via proxy → ${dlqTopic} (key=${key})`);
    return true;
  } catch (dlqErr) {
    console.error(
      `[Kafka] CRITICAL: DLQ publish failed for ${dlqTopic} (key=${key}) — event may be lost:`,
      (dlqErr as Error).message
    );
    return false;
  }
}

// ── Legacy per-message path (retry + DLQ) ────────────────────────────────────
// Used for proxy mode and as the fallback when a batched broker send fails, so
// round-7 semantics (bounded backoff → DLQ → explicit false) are preserved for
// every message that does not make it onto the broker via the fast batch path.
async function publishOneWithRetry<T>(
  topic: KafkaTopic,
  key: string,
  event: KafkaEvent<T>
): Promise<boolean> {
  let lastError: Error | null = null;
  for (let attempt = 1; attempt <= PUBLISH_MAX_ATTEMPTS; attempt++) {
    try {
      const producer = await getProducer();
      if (producer) {
        await producer.send({
          topic,
          messages: [{ key, value: JSON.stringify(event) }],
          compression: _compressionTypes?.GZIP,
        });
        return true;
      }
      await proxyPublish(topic, key, event);
      return true;
    } catch (err) {
      lastError = err as Error;
      if (attempt < PUBLISH_MAX_ATTEMPTS) {
        const backoffMs = publishBackoffMs(attempt);
        console.warn(
          `[Kafka] Publish ${topic} attempt ${attempt}/${PUBLISH_MAX_ATTEMPTS} failed (${lastError.message}); retrying in ${backoffMs}ms`
        );
        await sleep(backoffMs);
      }
    }
  }

  console.error(
    `[Kafka] Failed to publish ${topic} after ${PUBLISH_MAX_ATTEMPTS} attempts:`,
    lastError?.message
  );
  const deadLettered = await publishToDeadLetter(
    topic,
    key,
    event,
    lastError ?? new Error("unknown publish failure"),
    PUBLISH_MAX_ATTEMPTS
  );
  if (!deadLettered) {
    console.error(
      `[Kafka] CRITICAL: ${topic} event (key=${key}, eventId=${event.eventId}) was neither published nor dead-lettered`
    );
  }
  return false;
}

// ── Batched send accumulator ─────────────────────────────────────────────────
// publishEvent() enqueues; a single producer.send({ topicMessages }) flushes
// up to BATCH_MAX_MESSAGES messages (or after BATCH_LINGER_MS). This turns
// N broker round trips into 1 on the hot path.
const BATCH_LINGER_MS = 50;
const BATCH_MAX_MESSAGES = 100;

interface PendingPublish {
  topic: KafkaTopic;
  key: string;
  event: KafkaEvent<unknown>;
  resolve: (ok: boolean) => void;
}

let _pendingBatch: PendingPublish[] = [];
let _batchTimer: NodeJS.Timeout | null = null;
let _flushing = false;

async function flushPendingBatch(): Promise<void> {
  if (_flushing) return;
  _flushing = true;
  const batch = _pendingBatch;
  _pendingBatch = [];
  if (_batchTimer) {
    clearTimeout(_batchTimer);
    _batchTimer = null;
  }
  try {
    const producer = await getProducer();
    if (producer && batch.length > 0) {
      // Happy path: one send for the whole batch, grouped by topic.
      const byTopic = new Map<string, PendingPublish[]>();
      for (const p of batch) {
        const list = byTopic.get(p.topic) ?? [];
        list.push(p);
        byTopic.set(p.topic, list);
      }
      try {
        await producer.send({
          topicMessages: [...byTopic.entries()].map(([topic, items]) => ({
            topic,
            messages: items.map(i => ({
              key: i.key,
              value: JSON.stringify(i.event),
            })),
          })),
          compression: _compressionTypes?.GZIP,
        });
        for (const p of batch) p.resolve(true);
        return;
      } catch (err) {
        console.warn(
          `[Kafka] Batched send of ${batch.length} message(s) failed (${(err as Error).message}) — falling back to per-message retry/DLQ`
        );
        // Fall through to per-message handling below.
      }
    }
    // Proxy mode or batch failure: preserve round-7 per-message semantics.
    const results = await Promise.all(
      batch.map(p => publishOneWithRetry(p.topic, p.key, p.event))
    );
    results.forEach((ok, i) => batch[i].resolve(ok));
  } finally {
    _flushing = false;
    // Drain anything that arrived while we were flushing.
    if (_pendingBatch.length > 0) scheduleBatchFlush();
  }
}

function scheduleBatchFlush(): void {
  if (_batchTimer || _flushing) return;
  _batchTimer = setTimeout(() => {
    _batchTimer = null;
    void flushPendingBatch();
  }, BATCH_LINGER_MS);
  if (typeof _batchTimer.unref === "function") _batchTimer.unref();
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Publish a domain event to a Kafka topic.
 * The event joins the micro-batch accumulator (50ms / 100 messages) and is
 * flushed as one broker send. Retries with bounded exponential backoff; on
 * final failure the event is dead-lettered to "<topic>.dlq". Returns true on
 * success, false only after retries were exhausted and the DLQ path was
 * attempted (never silent).
 */
export function publishEvent<T>(
  topic: KafkaTopic,
  key: string,
  payload: T,
  metadata?: { agentCode?: string; tenantId?: string }
): Promise<boolean> {
  const event: KafkaEvent<T> = {
    eventId: crypto.randomUUID(),
    eventType: topic,
    timestamp: new Date().toISOString(),
    agentCode: metadata?.agentCode,
    tenantId: metadata?.tenantId,
    payload,
  };

  return new Promise<boolean>(resolve => {
    _pendingBatch.push({
      topic,
      key,
      event: event as KafkaEvent<unknown>,
      resolve,
    });
    if (_pendingBatch.length >= BATCH_MAX_MESSAGES) void flushPendingBatch();
    else scheduleBatchFlush();
  });
}

/**
 * Gracefully disconnect the Kafka producer.
 * Flushes any pending micro-batch first so queued events are not lost.
 * Called during graceful shutdown.
 */
export async function disconnectKafka(): Promise<void> {
  if (_pendingBatch.length > 0) {
    try {
      await flushPendingBatch();
    } catch {
      /* ignore */
    }
  }
  if (_producer) {
    try {
      await _producer.disconnect();
    } catch {
      /* ignore */
    }
    _producer = null;
  }
}

/**
 * Health check — returns true if Kafka is reachable.
 */
export async function kafkaIsHealthy(): Promise<boolean> {
  try {
    if (KAFKA_BROKERS) {
      const producer = await getProducer();
      return producer !== null;
    }
    const res = await fetch(`${PLATFORM_BASE_URL}/v1/events/topics`, {
      headers: { Authorization: `Bearer ${PLATFORM_API_KEY}` },
      signal: AbortSignal.timeout(2000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
