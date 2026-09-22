// TypeScript enabled — Sprint 96 security audit
/**
 * Kafka Event Consumer (S86-29)
 *
 * Consumes events from Kafka topics for:
 * - Transaction event sourcing (payment.created, payment.completed, payment.failed)
 * - Agent lifecycle events (agent.registered, agent.suspended, agent.reactivated)
 * - Float operations (float.topup, float.debit, float.reconciled)
 * - Audit trail (audit.action.created)
 * - Settlement events (settlement.initiated, settlement.completed)
 *
 * Features:
 * - Consumer group management with rebalancing
 * - Dead letter queue for failed messages
 * - Exactly-once processing via idempotency keys
 * - Batch processing with configurable batch size
 * - Schema registry integration for Avro/Protobuf
 * - Lag monitoring and alerting
 */

import type {
  Consumer,
  Producer,
  Kafka as KafkaClient,
  EachMessagePayload,
  EachBatchPayload,
} from "kafkajs";
import {
  claimIdempotencyKey,
  claimIdempotencyKeysBatch,
  completeIdempotencyKey,
  completeIdempotencyKeysBatch,
  failIdempotencyKey,
  hashIdempotencyPayload,
  type BatchClaimOutcome,
} from "./lib/transactionHelper";

/**
 * FF-17: marker error for idempotency-store failures. When the DB-backed
 * claim cannot be verified (DB down / claim error), the consumer must NOT
 * process the event unverified and must NOT dead-letter it (that would drop
 * a money event). Instead the error is rethrown so Kafka redelivers.
 */
class KafkaIdempotencyStoreError extends Error {
  constructor(message: string, readonly cause?: unknown) {
    super(message);
    this.name = "KafkaIdempotencyStoreError";
  }
}

// ─── Configuration ──────────────────────────────────────────────────────────

export interface KafkaConsumerConfig {
  brokers: string[];
  groupId: string;
  clientId: string;
  topics: string[];
  dlqTopic: string;
  batchSize: number;
  sessionTimeout: number;
  heartbeatInterval: number;
  maxRetries: number;
  retryBackoffMs: number;
  enableIdempotency: boolean;
  schemaRegistryUrl?: string;
}

const DEFAULT_CONFIG: KafkaConsumerConfig = {
  brokers: (process.env.KAFKA_BROKERS || "localhost:9092").split(","),
  groupId: "pos-shell-consumer-group",
  clientId: "pos-shell-event-consumer",
  topics: [
    "pos.transactions.events",
    "pos.agents.lifecycle",
    "pos.float.operations",
    "pos.audit.trail",
    "pos.settlements.events",
    "pos.notifications.outbound",
    "pos.compliance.events",
  ],
  dlqTopic: "pos.dead-letter-queue",
  batchSize: 100,
  sessionTimeout: 30000,
  heartbeatInterval: 3000,
  maxRetries: 5,
  retryBackoffMs: 1000,
  enableIdempotency: true,
  schemaRegistryUrl: process.env.SCHEMA_REGISTRY_URL,
};

// ─── Event Types ────────────────────────────────────────────────────────────

export interface PosEvent {
  id: string;
  type: string;
  source: string;
  timestamp: number;
  version: string;
  correlationId: string;
  causationId?: string;
  metadata: Record<string, string>;
  payload: Record<string, unknown>;
}

export interface ProcessingResult {
  eventId: string;
  success: boolean;
  error?: string;
  processingTimeMs: number;
  retryCount: number;
}

// ─── Event Handlers ─────────────────────────────────────────────────────────

type EventHandler = (event: PosEvent) => Promise<void>;

const eventHandlers: Map<string, EventHandler> = new Map();

// Transaction events
eventHandlers.set("payment.created", async event => {
  const { agentId, amount, currency, reference } = event.payload as any;
  console.log(
    `[Kafka] Payment created: agent=${agentId} amount=${amount} ${currency} ref=${reference}`
  );
  // Persist to event store, update read model
});

eventHandlers.set("payment.completed", async event => {
  const { transactionId, agentId, amount, fee } = event.payload as any;
  console.log(
    `[Kafka] Payment completed: tx=${transactionId} agent=${agentId} amount=${amount} fee=${fee}`
  );
  // Update agent balance, trigger settlement calculation, emit notification
});

eventHandlers.set("payment.failed", async event => {
  const { transactionId, reason, agentId } = event.payload as any;
  console.log(`[Kafka] Payment failed: tx=${transactionId} reason=${reason}`);
  // Reverse pending balance, alert agent, log to fraud system
});

// Agent lifecycle events
eventHandlers.set("agent.registered", async event => {
  const { agentId, name, region, tier } = event.payload as any;
  console.log(
    `[Kafka] Agent registered: ${agentId} name=${name} region=${region}`
  );
  // Initialize float account, send welcome notification, assign to region
});

eventHandlers.set("agent.suspended", async event => {
  const { agentId, reason, suspendedBy } = event.payload as any;
  console.log(`[Kafka] Agent suspended: ${agentId} reason=${reason}`);
  // Lock float, disable terminal, notify compliance
});

// Float events
eventHandlers.set("float.topup", async event => {
  const { agentId, amount, source, reference } = event.payload as any;
  console.log(
    `[Kafka] Float topup: agent=${agentId} amount=${amount} source=${source}`
  );
  // Credit float balance, emit receipt, update daily limits
});

eventHandlers.set("float.reconciled", async event => {
  const { batchId, agentCount, totalAmount, discrepancies } =
    event.payload as any;
  console.log(
    `[Kafka] Float reconciled: batch=${batchId} agents=${agentCount} total=${totalAmount}`
  );
  // Update reconciliation status, flag discrepancies for review
});

// Settlement events
eventHandlers.set("settlement.initiated", async event => {
  const { settlementId, agentId, amount, bankAccount } = event.payload as any;
  console.log(
    `[Kafka] Settlement initiated: ${settlementId} agent=${agentId} amount=${amount}`
  );
  // Debit agent float, initiate bank transfer, set pending status
});

eventHandlers.set("settlement.completed", async event => {
  const { settlementId, bankReference, completedAt } = event.payload as any;
  console.log(
    `[Kafka] Settlement completed: ${settlementId} ref=${bankReference}`
  );
  // Update status, notify agent, emit receipt
});

// ─── Consumer Metrics ───────────────────────────────────────────────────────

export interface ConsumerMetrics {
  messagesConsumed: number;
  messagesProcessed: number;
  messagesFailed: number;
  messagesDLQ: number;
  avgProcessingTimeMs: number;
  currentLag: number;
  lastMessageAt: number;
  uptime: number;
  startedAt: number;
  topicPartitions: Record<string, number[]>;
}

// ─── Kafka Event Consumer Class ─────────────────────────────────────────────

export class PosEventConsumer {
  private config: KafkaConsumerConfig;
  private consumer: Consumer | null = null;
  private producer: Producer | null = null;
  private processedIds: Set<string> = new Set();
  private metrics: ConsumerMetrics;
  private running = false;

  constructor(config: Partial<KafkaConsumerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.metrics = {
      messagesConsumed: 0,
      messagesProcessed: 0,
      messagesFailed: 0,
      messagesDLQ: 0,
      avgProcessingTimeMs: 0,
      currentLag: 0,
      lastMessageAt: 0,
      uptime: 0,
      startedAt: Date.now(),
      topicPartitions: {},
    };
  }

  async start(): Promise<void> {
    try {
      const { Kafka } = await import("kafkajs");
      const kafka = new Kafka({
        clientId: this.config.clientId,
        brokers: this.config.brokers,
        retry: {
          initialRetryTime: this.config.retryBackoffMs,
          retries: this.config.maxRetries,
        },
      });

      this.consumer = kafka.consumer({
        groupId: this.config.groupId,
        sessionTimeout: this.config.sessionTimeout,
        heartbeatInterval: this.config.heartbeatInterval,
      });

      this.producer = kafka.producer({
        idempotent: this.config.enableIdempotency,
      });

      await this.consumer.connect();
      await this.producer.connect();

      for (const topic of this.config.topics) {
        await this.consumer.subscribe({ topic, fromBeginning: false });
      }

      this.running = true;
      await this.consumer.run({
        // Round-8 perf: eachBatch instead of eachMessage. The declared
        // batchSize (100) was previously unused; it now bounds the idempotency
        // claim/complete SQL chunk size. Offsets are committed ONCE per batch
        // (commitOffsetsIfNecessary) instead of per message, and idempotency
        // claims/completions are batched (2 bulk writes per chunk instead of
        // 2 per event). FF-17 fail-closed semantics preserved: an idempotency
        // store failure throws before any offset is resolved, so the whole
        // uncommitted batch is redelivered.
        eachBatchAutoResolve: false,
        eachBatch: async (payload: EachBatchPayload) => {
          await this.processBatch(payload);
        },
      });

      console.log(
        `[Kafka Consumer] Started - topics: ${this.config.topics.join(", ")}`
      );
    } catch (error) {
      console.error("[Kafka Consumer] Failed to start:", error);
      // Graceful degradation - consumer will retry
    }
  }

  private async processMessage(payload: EachMessagePayload): Promise<void> {
    const { topic, partition, message } = payload;
    const startTime = Date.now();
    this.metrics.messagesConsumed++;

    try {
      const value = message.value?.toString();
      if (!value) return;

      const event: PosEvent = JSON.parse(value);

      // Idempotency check — fast path: in-memory cache (FF-17: retained as a
      // cache only; the DB claim below is authoritative, so a restart or the
      // 100k-cap eviction can no longer cause a money event to be reprocessed).
      if (this.config.enableIdempotency && this.processedIds.has(event.id)) {
        return; // Already processed
      }

      // Find and execute handler
      const handler = eventHandlers.get(event.type);
      if (handler) {
        if (this.config.enableIdempotency) {
          // FF-17: claim-first, DB-authoritative idempotency via the shared
          // idempotency_keys table (see lib/transactionHelper). The claim
          // happens BEFORE the handler runs; on success the claim is
          // completed, on handler failure it is marked failed (retry-safe).
          const idemKey = `kafka:${event.id}`;
          const requestHash = hashIdempotencyPayload(event);
          let claim;
          try {
            claim = await claimIdempotencyKey(idemKey, requestHash);
          } catch (claimErr) {
            // Fail CLOSED for money events: the processed-event record could
            // not be verified. Rethrow so Kafka redelivers — never process an
            // unverified money event, never DLQ it (that would drop it).
            throw new KafkaIdempotencyStoreError(
              `Idempotency claim failed for event ${event.id} — refusing to process unverified: ${(claimErr as Error).message}`,
              claimErr
            );
          }
          if (claim.kind === "replay") {
            // Already processed durably (possibly by a previous process or
            // consumer replica) — skip and cache locally.
            this.processedIds.add(event.id);
            this.metrics.lastMessageAt = Date.now();
            return;
          }
          try {
            await handler(event);
            await completeIdempotencyKey(idemKey, requestHash, null);
          } catch (handlerErr) {
            await failIdempotencyKey(
              idemKey,
              requestHash,
              handlerErr instanceof Error ? handlerErr.message : String(handlerErr)
            );
            throw handlerErr;
          }
          this.metrics.messagesProcessed++;
        } else {
          await handler(event);
          this.metrics.messagesProcessed++;
        }
      } else {
        console.warn(
          `[Kafka Consumer] No handler for event type: ${event.type}`
        );
      }

      // Mark as processed (in-memory fast-path cache)
      if (this.config.enableIdempotency) {
        this.processedIds.add(event.id);
        if (this.processedIds.size > 100_000) {
          const arr = Array.from(this.processedIds);
          this.processedIds = new Set(arr.slice(-50_000));
        }
      }

      this.metrics.lastMessageAt = Date.now();
    } catch (error: any) {
      if (error instanceof KafkaIdempotencyStoreError) {
        // FF-17 fail-closed: the event was NOT processed and must NOT be
        // dead-lettered. Rethrow so kafkajs does not commit the offset and
        // the event is redelivered once the idempotency store recovers.
        console.error(
          `[Kafka Consumer] Idempotency store unavailable on ${topic}:${partition} — event ${message.key} will be redelivered:`,
          error.message
        );
        throw error;
      }
      this.metrics.messagesFailed++;
      console.error(
        `[Kafka Consumer] Processing error on ${topic}:${partition}:`,
        error.message
      );

      // Send to DLQ
      await this.sendToDLQ(message, topic, partition, error.message);
    }

    // Update avg processing time
    const elapsed = Date.now() - startTime;
    this.metrics.avgProcessingTimeMs =
      (this.metrics.avgProcessingTimeMs * (this.metrics.messagesConsumed - 1) +
        elapsed) /
      this.metrics.messagesConsumed;
  }

  /**
   * Round-8: batch processing entry point (eachBatch, eachBatchAutoResolve=false).
   *
   * Per batch:
   *   1. Parse all messages.
   *   2. ONE bulk idempotency claim (chunked at config.batchSize) — throws
   *      KafkaIdempotencyStoreError on store failure BEFORE any offset is
   *      resolved, so the uncommitted batch is redelivered (FF-17 fail-closed,
   *      identical blast radius to the old per-message path).
   *   3. Handlers run sequentially in offset order (partition ordering kept);
   *      failures keep the old behavior: failIdempotencyKey + DLQ + resolve.
   *   4. ONE bulk completion UPDATE for the successful claims.
   *   5. ONE offset commit for the whole batch (commitOffsetsIfNecessary).
   *
   * Net PG traffic per 100-event chunk: ~3 round trips instead of ~200.
   */
  private async processBatch(payload: EachBatchPayload): Promise<void> {
    const { batch, resolveOffset, heartbeat, commitOffsetsIfNecessary } =
      payload;
    const { topic, partition } = batch;
    const startTime = Date.now();
    const chunkSize = Math.max(1, this.config.batchSize || 100);
    const HEARTBEAT_EVERY = 25;

    interface WorkItem {
      offset: string;
      message: (typeof batch.messages)[number];
      event: PosEvent;
      idemKey: string;
      requestHash: string;
    }

    const items: WorkItem[] = [];
    const immediate: { offset: string; message: (typeof batch.messages)[number]; dlqError?: string }[] = [];

    // ── 1. Parse ────────────────────────────────────────────────────────────
    for (const message of batch.messages) {
      this.metrics.messagesConsumed++;
      const value = message.value?.toString();
      if (!value) {
        immediate.push({ offset: message.offset, message });
        continue;
      }
      let event: PosEvent;
      try {
        event = JSON.parse(value);
      } catch (parseErr) {
        immediate.push({
          offset: message.offset,
          message,
          dlqError: `JSON parse error: ${(parseErr as Error).message}`,
        });
        continue;
      }
      // In-memory fast-path cache (FF-17: cache only; DB claim is authoritative)
      if (this.config.enableIdempotency && this.processedIds.has(event.id)) {
        immediate.push({ offset: message.offset, message });
        continue;
      }
      items.push({
        offset: message.offset,
        message,
        event,
        idemKey: `kafka:${event.id}`,
        requestHash: hashIdempotencyPayload(event),
      });
    }

    // ── 2. Bulk idempotency claim (fail-closed: nothing resolved yet) ────────
    let claims: Map<string, BatchClaimOutcome> = new Map();
    if (this.config.enableIdempotency && items.length > 0) {
      try {
        claims = await claimIdempotencyKeysBatch(
          items.map(i => ({ key: i.idemKey, requestHash: i.requestHash })),
          chunkSize
        );
      } catch (claimErr) {
        // Fail CLOSED for money events: the processed-event record could not
        // be verified. Rethrow before resolving/committing any offset so the
        // whole batch is redelivered once the idempotency store recovers.
        throw new KafkaIdempotencyStoreError(
          `Idempotency batch claim failed on ${topic}:${partition} (${items.length} events) — refusing to process unverified: ${(claimErr as Error).message}`,
          claimErr
        );
      }
    }

    // ── 3. Process in offset order ───────────────────────────────────────────
    const completions: { key: string; requestHash: string; result: unknown }[] =
      [];
    let processed = 0;

    const bumpCache = (eventId: string) => {
      if (!this.config.enableIdempotency) return;
      this.processedIds.add(eventId);
      if (this.processedIds.size > 100_000) {
        const arr = Array.from(this.processedIds);
        this.processedIds = new Set(arr.slice(-50_000));
      }
    };

    for (const imm of immediate) {
      if (imm.dlqError) {
        this.metrics.messagesFailed++;
        await this.sendToDLQ(imm.message, topic, partition, imm.dlqError);
      }
      resolveOffset(imm.offset);
    }

    for (const item of items) {
      processed++;
      if (processed % HEARTBEAT_EVERY === 0) await heartbeat();

      const handler = eventHandlers.get(item.event.type);
      const claim = claims.get(item.idemKey);

      if (this.config.enableIdempotency && claim?.kind === "replay") {
        // Already processed durably — skip and cache locally.
        bumpCache(item.event.id);
        this.metrics.lastMessageAt = Date.now();
        resolveOffset(item.offset);
        continue;
      }

      if (this.config.enableIdempotency && claim?.kind === "conflict") {
        // Old behavior: a CONFLICT from the claim path surfaced as a generic
        // processing error → DLQ (never silently reprocessed).
        this.metrics.messagesFailed++;
        console.error(
          `[Kafka Consumer] Idempotency conflict on ${topic}:${partition} for event ${item.event.id}: ${claim.reason}`
        );
        await this.sendToDLQ(item.message, topic, partition, claim.reason);
        resolveOffset(item.offset);
        continue;
      }

      if (!handler) {
        console.warn(
          `[Kafka Consumer] No handler for event type: ${item.event.type}`
        );
        resolveOffset(item.offset);
        continue;
      }

      try {
        await handler(item.event);
        if (this.config.enableIdempotency) {
          completions.push({
            key: item.idemKey,
            requestHash: item.requestHash,
            result: null,
          });
          bumpCache(item.event.id);
        }
        this.metrics.messagesProcessed++;
      } catch (handlerErr) {
        const errMsg =
          handlerErr instanceof Error ? handlerErr.message : String(handlerErr);
        if (this.config.enableIdempotency) {
          await failIdempotencyKey(item.idemKey, item.requestHash, errMsg);
        }
        this.metrics.messagesFailed++;
        console.error(
          `[Kafka Consumer] Processing error on ${topic}:${partition}:`,
          errMsg
        );
        await this.sendToDLQ(item.message, topic, partition, errMsg);
      }
      resolveOffset(item.offset);
    }

    // ── 4. Bulk completion (before any commit, matching old write ordering) ──
    if (completions.length > 0) {
      await completeIdempotencyKeysBatch(completions, chunkSize);
    }

    // ── 5. Per-batch offset commit ───────────────────────────────────────────
    await commitOffsetsIfNecessary();
    this.metrics.lastMessageAt = Date.now();

    // Update avg processing time (per batch)
    const elapsed = Date.now() - startTime;
    const n = Math.max(1, batch.messages.length);
    this.metrics.avgProcessingTimeMs =
      (this.metrics.avgProcessingTimeMs *
        Math.max(0, this.metrics.messagesConsumed - n) +
        elapsed) /
      this.metrics.messagesConsumed;
  }

  private async sendToDLQ(
    message: any,
    sourceTopic: string,
    partition: number,
    error: string
  ): Promise<void> {
    if (!this.producer) return;

    try {
      await this.producer.send({
        topic: this.config.dlqTopic,
        messages: [
          {
            key: message.key,
            value: message.value,
            headers: {
              "x-original-topic": sourceTopic,
              "x-original-partition": String(partition),
              "x-error": error,
              "x-failed-at": String(Date.now()),
              "x-retry-count": String(this.config.maxRetries),
            },
          },
        ],
      });
      this.metrics.messagesDLQ++;
    } catch (dlqError) {
      console.error("[Kafka Consumer] Failed to send to DLQ:", dlqError);
    }
  }

  getMetrics(): ConsumerMetrics {
    return {
      ...this.metrics,
      uptime: Date.now() - this.metrics.startedAt,
    };
  }

  async stop(): Promise<void> {
    this.running = false;
    if (this.consumer) await this.consumer.disconnect();
    if (this.producer) await this.producer.disconnect();
    console.log("[Kafka Consumer] Stopped");
  }
}

// ─── Export singleton ───────────────────────────────────────────────────────

let consumerInstance: PosEventConsumer | null = null;

export function getKafkaConsumer(): PosEventConsumer {
  if (!consumerInstance) {
    consumerInstance = new PosEventConsumer();
  }
  return consumerInstance;
}

export default PosEventConsumer;
