/**
 * batchedAsyncQueue.ts — shared micro-batching helper for fire-and-forget
 * observability/audit fan-out.
 *
 * Replaces per-request fire-and-forget network calls (Kafka single-message
 * sends, Redis SETs, sidecar HTTP POSTs) with an in-memory queue that is
 * flushed:
 *   - every FLUSH_INTERVAL_MS (default 100ms), or
 *   - as soon as BATCH_SIZE (default 50) items are buffered.
 *
 * Each flush is bounded by TASK_TIMEOUT_MS (default 500ms) — a slow sink
 * drops the batch rather than backing up the event loop.
 *
 * Backpressure: when MAX_QUEUE (default 10_000) buffered items is exceeded,
 * the OLDEST items are dropped (observability data is best-effort; shedding
 * load beats OOM-ing the process).
 *
 * The queue is fully in-process: events are lost on crash/shutdown. That is
 * acceptable for telemetry and audit-copy fan-out; durable audit trails must
 * keep using writeAuditLog/outbox paths.
 */

import logger from "../_core/logger";

export interface BatchedQueueOptions<T> {
  /** Flush trigger: buffered item count. Default 50. */
  batchSize?: number;
  /** Flush trigger: max wait in ms. Default 100. */
  flushIntervalMs?: number;
  /** Hard cap on buffered items; oldest dropped beyond this. Default 10_000. */
  maxQueue?: number;
  /** Max time a single flush may take before it is abandoned. Default 500. */
  taskTimeoutMs?: number;
  /** Human-readable name for log lines. */
  name?: string;
  /** The sink. Receives up to batchSize items; errors are swallowed+logged. */
  flush: (batch: T[]) => Promise<void> | void;
}

export interface BatchedQueue<T> {
  push: (item: T) => void;
  /** Flush now (used by tests and graceful shutdown). */
  flushNow: () => Promise<void>;
  size: () => number;
  droppedTotal: () => number;
}

export function createBatchedQueue<T>(
  options: BatchedQueueOptions<T>
): BatchedQueue<T> {
  const batchSize = options.batchSize ?? 50;
  const flushIntervalMs = options.flushIntervalMs ?? 100;
  const maxQueue = options.maxQueue ?? 10_000;
  const taskTimeoutMs = options.taskTimeoutMs ?? 500;
  const name = options.name ?? "batchedQueue";

  let buffer: T[] = [];
  let timer: NodeJS.Timeout | null = null;
  let flushing = false;
  let dropped = 0;

  function schedule(): void {
    if (timer || flushing) return;
    timer = setTimeout(() => {
      timer = null;
      void doFlush();
    }, flushIntervalMs);
    // Never keep the process alive for telemetry.
    if (typeof timer.unref === "function") timer.unref();
  }

  async function doFlush(): Promise<void> {
    if (flushing || buffer.length === 0) return;
    flushing = true;
    const batch = buffer.slice(0, batchSize);
    buffer = buffer.slice(batch.length);
    try {
      await Promise.race([
        Promise.resolve().then(() => options.flush(batch)),
        new Promise<void>((_, reject) =>
          setTimeout(
            () => reject(new Error(`flush timed out after ${taskTimeoutMs}ms`)),
            taskTimeoutMs
          )
        ),
      ]);
    } catch (err) {
      // Fire-and-forget: a failing sink drops the batch, never the request path.
      dropped += batch.length;
      logger.warn(
        { queue: name, err: String(err), batchSize: batch.length },
        `[${name}] flush failed — batch dropped`
      );
    } finally {
      flushing = false;
      if (buffer.length > 0) {
        // Drain remaining backlog promptly (respecting batchSize per flush).
        if (buffer.length >= batchSize) void doFlush();
        else schedule();
      }
    }
  }

  return {
    push(item: T): void {
      if (buffer.length >= maxQueue) {
        buffer.shift();
        dropped++;
      }
      buffer.push(item);
      if (buffer.length >= batchSize) void doFlush();
      else schedule();
    },
    async flushNow(): Promise<void> {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      while (buffer.length > 0) {
        await doFlush();
      }
    },
    size: () => buffer.length,
    droppedTotal: () => dropped,
  };
}
