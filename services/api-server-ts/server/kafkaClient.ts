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
import type { Kafka as KafkaType, Producer } from "kafkajs";
import { ENV } from "./_core/env";
let _kafka: KafkaType | null = null;
let _producer: Producer | null = null;

async function getProducer(): Promise<Producer | null> {
  if (_producer) return _producer;
  try {
    const { Kafka } = await import("kafkajs");
    _kafka = new Kafka({
      clientId: KAFKA_CLIENT_ID,
      brokers: KAFKA_BROKERS.split(",").map(b => b.trim()),
      retry: { retries: 3 },
    });
    _producer = _kafka.producer({ allowAutoTopicCreation: false });
    await _producer.connect();
    console.log("[Kafka] Producer connected →", KAFKA_BROKERS);
    return _producer;
  } catch (err) {
    console.warn("[Kafka] Could not connect producer:", (err as Error).message);
    return null;
  }
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
  | "pos.fraud.alert_raised";

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

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Publish a domain event to a Kafka topic.
 * Retries with bounded exponential backoff; on final failure the event is
 * dead-lettered to "<topic>.dlq". Returns true on success, false only after
 * retries were exhausted and the DLQ path was attempted (never silent).
 */
export async function publishEvent<T>(
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

  let lastError: Error | null = null;
  for (let attempt = 1; attempt <= PUBLISH_MAX_ATTEMPTS; attempt++) {
    try {
      const producer = await getProducer();
      if (producer) {
        await producer.send({
          topic,
          messages: [{ key, value: JSON.stringify(event) }],
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

/**
 * Gracefully disconnect the Kafka producer.
 * Called during graceful shutdown.
 */
export async function disconnectKafka(): Promise<void> {
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
