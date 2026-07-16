// TypeScript enabled — Sprint 96 security audit
// SECURITY: SQL template literals in this file are for display/mock purposes only. All actual DB queries use parameterized Drizzle ORM.
/**
 * 54agent Fluvio Client
 * Connects to Fluvio via its HTTP gateway (no native SDK required).
 * Used for real-time fraud stream processing.
 *
 * Architecture:
 *   Kafka tx.created → Fluvio SmartModule (velocity + anomaly check) → fraud.alert topic
 *   Node.js consumer → DB insert + push notification
 *
 * Audit: All produced events are logged to the fluvio_event_log PostgreSQL
 * table (migration 0047) for reconciliation and replay capability.
 *
 * Environment variables:
 *   FLUVIO_HTTP_URL — Full URL of the Fluvio HTTP gateway
 *                     (default: http://fluvio-http-gateway:9090 in production,
 *                      http://localhost:9090 in development)
 */
import logger from "./_core/logger";

// In production, FLUVIO_HTTP_URL is set to http://fluvio-http-gateway:9090
// via the app service environment in docker-compose.production.yml
const FLUVIO_HTTP_URL = process.env.FLUVIO_HTTP_URL ?? "http://localhost:9090";
const FLUVIO_TOPIC_FRAUD = "fraud.alert";
const FLUVIO_TOPIC_TX = "tx.created";

interface FluvioRecord {
  key?: string;
  value: string;
}

/**
 * Persist a Fluvio event to the fluvio_event_log table for audit/reconciliation.
 * Fire-and-forget — never blocks the produce path.
 */
async function persistEventToDb(
  topic: string,
  record: FluvioRecord,
  eventType: string,
  agentCode?: string,
  txRef?: string,
  status: "produced" | "failed" = "produced",
  errorMessage?: string
): Promise<void> {
  try {
    const { getDb } = await import("./db");
    const { fluvioEventLog } = await import("../drizzle/schema");
    const db = await getDb();
    if (!db) return;
    let payload: Record<string, unknown> = {};
    try {
      payload = JSON.parse(record.value);
    } catch {
      payload = { raw: record.value };
    }
    await db.insert(fluvioEventLog).values({
      topic,
      key: record.key,
      payload,
      eventType,
      agentCode,
      txRef,
      status,
      errorMessage,
    });
  } catch {
    // Persistence failure must never break the Fluvio produce path
  }
}

/**
 * Produce a record to a Fluvio topic via HTTP gateway.
 */
export async function fluvioProduce(
  topic: string,
  record: FluvioRecord,
  eventType?: string,
  agentCode?: string,
  txRef?: string
): Promise<void> {
  try {
    const res = await fetch(`${FLUVIO_HTTP_URL}/produce/${topic}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(record),
      signal: AbortSignal.timeout(3_000),
    });
    if (!res.ok) {
      logger.warn(`[Fluvio] Produce to ${topic} failed: ${res.status}`);
      if (eventType) {
        void persistEventToDb(topic, record, eventType, agentCode, txRef, "failed", `HTTP ${res.status}`);
      }
    } else if (eventType) {
      void persistEventToDb(topic, record, eventType, agentCode, txRef, "produced");
    }
  } catch (err) {
    logger.warn(
      { err },
      `[Fluvio] Produce to ${topic} unavailable — event dropped`
    );
    if (eventType) {
      void persistEventToDb(topic, record, eventType, agentCode, txRef, "failed", String(err));
    }
  }
}

/**
 * Publish a transaction event to the Fluvio tx.created topic.
 * The Fluvio SmartModule will apply velocity and anomaly checks.
 */
export async function publishTxToFluvio(tx: {
  txRef: string;
  agentCode: string;
  amount: number;
  type: string;
  customerPhone?: string;
  timestamp: number;
}): Promise<void> {
  await fluvioProduce(
    FLUVIO_TOPIC_TX,
    { key: tx.agentCode, value: JSON.stringify(tx) },
    "tx.created",
    tx.agentCode,
    tx.txRef
  );
}

/**
 * Publish a fraud alert to the Fluvio fraud.alert topic.
 */
export async function publishFraudAlert(alert: {
  txRef: string;
  agentCode: string;
  severity: string;
  reason: string;
  amount: number;
}): Promise<void> {
  await fluvioProduce(
    FLUVIO_TOPIC_FRAUD,
    { key: alert.agentCode, value: JSON.stringify({ ...alert, timestamp: Date.now() }) },
    "fraud.alert",
    alert.agentCode,
    alert.txRef
  );
}

/**
 * Publish a workflow event (used by the Go workflow orchestrator bridge).
 */
export async function publishWorkflowEvent(event: {
  workflowId: string;
  type: string;
  payload: object;
}): Promise<void> {
  await fluvioProduce(
    "workflow.events",
    { key: event.workflowId, value: JSON.stringify(event) },
    event.type
  );
}

export default { publishTxToFluvio, publishFraudAlert, publishWorkflowEvent };
