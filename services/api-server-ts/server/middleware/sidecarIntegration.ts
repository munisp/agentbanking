// TypeScript enabled — Sprint 96 security audit
/**
 * sidecarIntegration.ts — tRPC middleware that automatically integrates
 * all procedures with the Rust/Go/Python sidecars.
 *
 * Applied globally via appRouter, this ensures every procedure:
 * 1. Gets audit-logged (Rust sidecar)
 * 2. Gets Kafka event published (Rust sidecar)
 * 3. Gets rate-limited (Rust sidecar)
 * 4. Has access to ledger, ML, and compliance via ctx
 *
 * Uses factory pattern (same as observabilityMiddleware) to avoid circular deps.
 */

import { initTRPC } from "@trpc/server";
import type { TrpcContext } from "../_core/context";
import {
  rustBridge,
  goLedger,
  pythonML,
  emitTransactionEvent,
  auditAndCache,
  runCompliancePipeline,
} from "../lib/sidecarBridge";
import { createBatchedQueue } from "../lib/batchedAsyncQueue";

/**
 * ROUND-8 PERF: the per-request fire-and-forget HTTP calls to the Rust
 * sidecar (rateLimit + auditLog pre, kafkaPublish post) are now pushed onto
 * a shared batched async queue (flush every 100ms / 50 events, 500ms timeout,
 * drop-oldest backpressure at 10k). The request path cost is an array push
 * instead of 3 socket acquisitions per procedure call.
 *
 * NOTE: the rateLimit result was always fire-and-forget ({allowed:true}
 * fallback) and never gated requests; batching preserves that behavior.
 */
type SidecarTask =
  | { kind: "rateLimit"; key: string }
  | { kind: "auditLog"; userId: string; action: string; resource: string }
  | {
      kind: "kafkaPublish";
      topic: string;
      key: string;
      payload: unknown;
    };

async function flushSidecarBatch(tasks: SidecarTask[]): Promise<void> {
  await Promise.allSettled(
    tasks.map(task => {
      switch (task.kind) {
        case "rateLimit":
          return rustBridge.rateLimit(task.key, 100, 60);
        case "auditLog":
          return rustBridge.auditLog(task.userId, task.action, task.resource);
        case "kafkaPublish":
          return rustBridge.kafkaPublish(task.topic, task.key, task.payload);
      }
    })
  );
}

const sidecarQueue = createBatchedQueue<SidecarTask>({
  name: "sidecarIntegration",
  batchSize: 50,
  flushIntervalMs: 100,
  maxQueue: 10_000,
  taskTimeoutMs: 500,
  flush: flushSidecarBatch,
});

/** Flush pending sidecar tasks (graceful shutdown / tests). */
export async function flushSidecarQueue(): Promise<void> {
  await sidecarQueue.flushNow();
}

/**
 * Factory: creates the global sidecar integration middleware.
 * Call once from _core/trpc.ts, passing the tRPC instance.
 */
export function createSidecarMiddleware(t: any) {
  return t.middleware(
    async ({
      ctx,
      path,
      type,
      next,
    }: {
      ctx: any;
      path: string;
      type: string;
      next: any;
    }) => {
      const startTime = Date.now();
      const userId = (ctx as any)?.user?.id?.toString() ?? "anonymous";
      const procedurePath = path;

      // Pre-execution: Rate limiting via Rust sidecar (queued, fail-open)
      sidecarQueue.push({
        kind: "rateLimit",
        key: `trpc:${userId}:${procedurePath}`,
      });

      // Pre-execution: Audit log via Rust sidecar (queued, fail-open)
      sidecarQueue.push({ kind: "auditLog", userId, action: type, resource: procedurePath });

      // Execute the actual procedure with sidecar clients injected into context
      const result = await next({
        ctx: {
          ...ctx,
          sidecars: {
            rust: rustBridge,
            go: goLedger,
            python: pythonML,
            emitTransaction: emitTransactionEvent,
            auditAndCache,
            runCompliance: runCompliancePipeline,
          },
        },
      });

      // Post-execution: Publish event to Kafka via Rust sidecar (queued,
      // fail-open). "pos.trpc.events" is the single existing topic for these
      // procedure-execution events (unchanged from before round-8).
      const duration = Date.now() - startTime;
      sidecarQueue.push({
        kind: "kafkaPublish",
        topic: "pos.trpc.events",
        key: userId,
        payload: {
          procedure: procedurePath,
          type,
          userId,
          duration,
          success: result.ok,
          timestamp: Date.now(),
        },
      });

      return result;
    }
  );
}
