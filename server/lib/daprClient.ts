/**
 * Dapr Sidecar Client
 * Pub/sub messaging and state store operations via Dapr HTTP API.
 * Fail-open: returns gracefully when Dapr sidecar is unavailable.
 *
 * The Dapr sidecar (app-dapr service in docker-compose.production.yml) runs
 * in network_mode:service:app, sharing the network namespace with the app
 * container. This means the sidecar is always reachable at localhost:3500.
 *
 * Audit: All pub/sub publish calls are logged to the dapr_pubsub_log
 * PostgreSQL table (migration 0047) for message tracing and dead-letter analysis.
 *
 * Environment variables:
 *   DAPR_HTTP_PORT  — Dapr sidecar HTTP port (default: 3500, injected by compose)
 *   DAPR_GRPC_PORT  — Dapr sidecar gRPC port (default: 50001, injected by compose)
 *   DAPR_URL        — Full base URL override (default: http://localhost:${DAPR_HTTP_PORT})
 *   DAPR_APP_ID     — This app's Dapr app ID (default: pos-shell)
 */

// DAPR_HTTP_PORT is injected by the app-dapr sidecar container in docker-compose.production.yml
const DAPR_HTTP_PORT = process.env.DAPR_HTTP_PORT ?? "3500";
const DAPR_URL = process.env.DAPR_URL ?? `http://localhost:${DAPR_HTTP_PORT}`;
const DAPR_APP_ID = process.env.DAPR_APP_ID ?? "pos-shell";

/**
 * Persist a Dapr pub/sub event to the dapr_pubsub_log table.
 * Fire-and-forget — never blocks the publish path.
 */
async function persistPubsubLog(opts: {
  pubsubName: string;
  topic: string;
  payload: Record<string, unknown>;
  status: "published" | "failed";
  errorMessage?: string;
  agentCode?: string;
  txRef?: string;
  correlationId?: string;
}): Promise<void> {
  try {
    const { getDb } = await import("../db");
    const { daprPubsubLog } = await import("../../drizzle/schema");
    const db = await getDb();
    if (!db) return;
    await db.insert(daprPubsubLog).values({
      pubsubName: opts.pubsubName,
      topic: opts.topic,
      direction: "publish",
      appId: DAPR_APP_ID,
      payload: opts.payload,
      status: opts.status,
      errorMessage: opts.errorMessage,
      agentCode: opts.agentCode,
      txRef: opts.txRef,
      correlationId: opts.correlationId,
    });
  } catch {
    // Persistence failure must never break the pub/sub path
  }
}

export async function daprPublish(
  pubsubName: string,
  topic: string,
  data: Record<string, unknown>
): Promise<boolean> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/publish/${pubsubName}/${topic}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(5000),
      }
    );
    const ok = response.ok;
    // Log all pub/sub events for audit and dead-letter analysis
    void persistPubsubLog({
      pubsubName,
      topic,
      payload: data,
      status: ok ? "published" : "failed",
      errorMessage: ok ? undefined : `HTTP ${response.status}`,
      agentCode: typeof data.agentCode === "string" ? data.agentCode : undefined,
      txRef: typeof data.txRef === "string" ? data.txRef :
             typeof data.transactionRef === "string" ? data.transactionRef : undefined,
      correlationId: typeof data.correlationId === "string" ? data.correlationId : undefined,
    });
    return ok;
  } catch (err) {
    void persistPubsubLog({
      pubsubName,
      topic,
      payload: data,
      status: "failed",
      errorMessage: String(err),
      agentCode: typeof data.agentCode === "string" ? data.agentCode : undefined,
      txRef: typeof data.txRef === "string" ? data.txRef : undefined,
    });
    return false;
  }
}

export async function daprStateGet(
  storeName: string,
  key: string
): Promise<unknown | null> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/state/${storeName}/${key}`,
      { signal: AbortSignal.timeout(3000) }
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function daprStateSave(
  storeName: string,
  key: string,
  value: unknown
): Promise<boolean> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/state/${storeName}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([{ key, value }]),
        signal: AbortSignal.timeout(5000),
      }
    );
    return response.ok;
  } catch {
    return false;
  }
}

export async function daprInvokeService(
  appId: string,
  method: string,
  data?: unknown
): Promise<unknown | null> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/invoke/${appId}/method/${method}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: data ? JSON.stringify(data) : undefined,
        signal: AbortSignal.timeout(10000),
      }
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

/**
 * Check Dapr sidecar health — used by readiness probes and health endpoints.
 */
export async function daprHealthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${DAPR_URL}/v1.0/healthz`, {
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Subscribe to a Dapr pub/sub topic (for use in worker processes).
 * Returns the list of subscriptions to register with the Dapr sidecar.
 */
export function getDaprSubscriptions(): Array<{
  pubsubname: string;
  topic: string;
  route: string;
}> {
  return [
    {
      pubsubname: "54link-pubsub",
      topic: "settlement.trigger",
      route: "/dapr/subscribe/settlement",
    },
    {
      pubsubname: "54link-pubsub",
      topic: "kyc.approved",
      route: "/dapr/subscribe/kyc",
    },
    {
      pubsubname: "54link-pubsub",
      topic: "fraud.alert",
      route: "/dapr/subscribe/fraud",
    },
    {
      pubsubname: "54link-pubsub",
      topic: "float.replenishment",
      route: "/dapr/subscribe/float",
    },
    {
      pubsubname: "54link-pubsub",
      topic: "commission.payout",
      route: "/dapr/subscribe/commission",
    },
  ];
}
