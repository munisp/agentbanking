// TypeScript enabled — Sprint 96 security audit
/**
 * observabilityMiddleware.ts — tRPC middleware that automatically instruments
 * ALL procedures with Kafka event publishing, Redis last-call timestamps, and
 * Fluvio streaming.
 *
 * This is applied at the procedure level via tRPC's middleware chain, so
 * individual routers do NOT need to import or call any middleware functions.
 *
 * ROUND-8 PERF REWORK:
 *  - The per-request fire-and-forget fan-out (Kafka single-send + Redis SET +
 *    Fluvio HTTP POST + TigerBeetle zero-amount transfer) is replaced by an
 *    in-memory batched queue (server/lib/batchedAsyncQueue.ts): the request
 *    path is now a single array push; flush happens every 100ms / 50 events
 *    with a 500ms timeout and drop-oldest backpressure at 10k events.
 *  - The zero-amount TigerBeetle "audit" transfer was REMOVED — fabricated
 *    bookkeeping (observability is not money movement; flooding the ledger
 *    with 0-amount transfers per request was pure cost).
 *  - Kafka events now go to ONE existing topic ("pos.audit.trail", consumed
 *    by kafka-event-consumer's default config) instead of ad-hoc per-path
 *    topics that failed under allowAutoTopicCreation:false and churned
 *    4× backoff + DLQ per request.
 *
 * All calls remain fail-open: queue flush errors are logged and dropped,
 * never propagated to the request path.
 */
import { publishEvent } from "../kafkaClient";
import { cacheSet } from "../redisClient";
import { fluvioProduce } from "../fluvio";
import { createBatchedQueue } from "../lib/batchedAsyncQueue";

// ── Observability Middleware ──────────────────────────────────────────────────
// Wraps every procedure call with a batched (queued) observability event:
// 1. Kafka event publish (batched via kafkaClient micro-batch)
// 2. Redis cache of last-call timestamp
// 3. Fluvio real-time stream event
//
// The TigerBeetle zero-amount audit transfer was removed in round 8 (see header).

export interface ObservabilityContext {
  /** The router path, e.g. "agent.login" */
  path: string;
  /** The procedure type: "query" | "mutation" | "subscription" */
  type: string;
  /** The user ID if authenticated, or "anonymous" */
  userId: string;
  /** Start timestamp */
  startMs: number;
  /** Duration in ms */
  durationMs: number;
  /** Whether the procedure succeeded */
  success: boolean;
  /** Error message if failed */
  error?: string;
}

/** Single existing topic for all tRPC observability events. */
const OBSERVABILITY_KAFKA_TOPIC = "pos.audit.trail" as const;
/** Single Fluvio topic for tRPC observability events (was per-path ad-hoc). */
const OBSERVABILITY_FLUVIO_TOPIC = "pos.trpc.events";

/**
 * Flush a batch of observability events to all sinks.
 * Invoked by the queue (100ms / 50 events), bounded to 500ms by the queue.
 * Individual sink failures are swallowed (fail-open).
 */
async function flushObservabilityBatch(
  events: ObservabilityContext[]
): Promise<void> {
  await Promise.allSettled(
    events.map(async ctx => {
      const payload = {
        path: ctx.path,
        type: ctx.type,
        userId: ctx.userId,
        durationMs: ctx.durationMs,
        success: ctx.success,
        error: ctx.error,
        timestamp: Date.now(),
      };

      // 1. Kafka — event bus for downstream consumers (analytics, audit,
      //    alerting). kafkaClient itself micro-batches these into a single
      //    producer.send per 50ms window.
      try {
        await publishEvent(OBSERVABILITY_KAFKA_TOPIC, ctx.userId, {
          event: `${ctx.path}.${ctx.success ? "success" : "failure"}`,
          ...payload,
        });
      } catch {}

      // 2. Redis — cache last-call timestamp for rate limiting and monitoring
      try {
        await cacheSet(
          `obs:${ctx.path}:${ctx.userId}:last`,
          JSON.stringify({
            ts: Date.now(),
            duration: ctx.durationMs,
            success: ctx.success,
          }),
          600 // 10 min TTL
        );
      } catch {}

      // 3. Fluvio — real-time streaming for dashboards and alerting
      try {
        await fluvioProduce(OBSERVABILITY_FLUVIO_TOPIC, {
          value: JSON.stringify(payload),
        });
      } catch {}
    })
  );
}

// Batched async queue: request path = one array push. Flush every 100ms or
// 50 events; 500ms timeout per flush; drop-oldest backpressure at 10k.
const observabilityQueue = createBatchedQueue<ObservabilityContext>({
  name: "observability",
  batchSize: 50,
  flushIntervalMs: 100,
  maxQueue: 10_000,
  taskTimeoutMs: 500,
  flush: flushObservabilityBatch,
});

/**
 * Enqueue an observability event. Never blocks; the request path cost is a
 * single array push. Kept async-shaped for backwards compatibility with
 * existing call sites (they `.catch()` the returned promise).
 */
export async function emitObservabilityEvent(
  ctx: ObservabilityContext
): Promise<void> {
  observabilityQueue.push(ctx);
}

/** Flush pending observability events (graceful shutdown / tests). */
export async function flushObservabilityQueue(): Promise<void> {
  await observabilityQueue.flushNow();
}

/**
 * Create the observability tRPC middleware.
 * This can be chained onto any procedure base.
 */
export function createObservabilityMiddleware(t: any) {
  return t.middleware(
    async ({
      ctx,
      next,
      path,
      type,
    }: {
      ctx: any;
      next: any;
      path: string;
      type: string;
    }) => {
      const startMs = Date.now();
      const userId = ctx.user ? String(ctx.user.id) : "anonymous";

      try {
        const result = await next({ ctx });
        const durationMs = Date.now() - startMs;

        // Queue push: O(1), off the response path
        emitObservabilityEvent({
          path,
          type,
          userId,
          startMs,
          durationMs,
          success: true,
        }).catch(() => {}); // swallow any unhandled rejection

        return result;
      } catch (error) {
        const durationMs = Date.now() - startMs;

        emitObservabilityEvent({
          path,
          type,
          userId,
          startMs,
          durationMs,
          success: false,
          error: error instanceof Error ? error.message : String(error),
        }).catch(() => {});

        throw error; // re-throw to preserve tRPC error handling
      }
    }
  );
}
