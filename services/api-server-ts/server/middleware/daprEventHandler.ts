/**
 * Dapr Event Handler — 54agent Platform
 *
 * Handles incoming Dapr pub/sub events via HTTP endpoints.
 * Processes transaction events, fraud alerts, settlement notifications,
 * and agent lifecycle events from Kafka via Dapr sidecar.
 */

export interface DaprCloudEvent<T = unknown> {
  id: string;
  source: string;
  type: string;
  specversion: string;
  datacontenttype: string;
  data: T;
  topic: string;
  pubsubname: string;
  traceid?: string;
}

type EventHandler<T = unknown> = (event: DaprCloudEvent<T>) => Promise<void>;

const handlers = new Map<string, EventHandler[]>();
const deadLetterQueue: Array<{
  event: DaprCloudEvent;
  error: string;
  timestamp: string;
}> = [];

export function onEvent<T = unknown>(
  topic: string,
  handler: EventHandler<T>
): void {
  const existing = handlers.get(topic) ?? [];
  existing.push(handler as EventHandler);
  handlers.set(topic, existing);
}

export async function processEvent(event: DaprCloudEvent): Promise<{
  status: "SUCCESS" | "RETRY" | "DROP";
}> {
  const topicHandlers = handlers.get(event.topic) ?? [];
  if (topicHandlers.length === 0) {
    console.warn(`[Dapr] No handlers registered for topic: ${event.topic}`);
    return { status: "DROP" };
  }

  for (const handler of topicHandlers) {
    try {
      await handler(event);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error(`[Dapr] Handler error for ${event.topic}:`, errorMsg);
      deadLetterQueue.push({
        event,
        error: errorMsg,
        timestamp: new Date().toISOString(),
      });
      if (deadLetterQueue.length > 1000) deadLetterQueue.shift();
      return { status: "RETRY" };
    }
  }

  return { status: "SUCCESS" };
}

export function getDeadLetterQueue() {
  return [...deadLetterQueue];
}

export function getSubscriptions() {
  return Array.from(handlers.keys()).map(topic => ({
    pubsubname: "kafka-pubsub",
    topic,
    route: `/api/events/${topic.replace("pos.", "")}`,
  }));
}

// ── Default Event Handlers ───────────────────────────────────────────────────

onEvent("pos.transactions", async event => {
  const data = event.data as Record<string, unknown>;
  console.log(
    `[Dapr] Transaction event: ${data.transactionId} — ${data.type} — ${data.status}`
  );
});

onEvent("pos.fraud-alerts", async event => {
  const data = event.data as Record<string, unknown>;
  console.log(
    `[Dapr] Fraud alert: ${data.alertId} — severity: ${data.severity} — score: ${data.riskScore}`
  );
});

onEvent("pos.settlements", async event => {
  const data = event.data as Record<string, unknown>;
  console.log(`[Dapr] Settlement event: ${data.settlementId} — ${data.status}`);
});

onEvent("pos.agents", async event => {
  const data = event.data as Record<string, unknown>;
  console.log(`[Dapr] Agent event: ${data.agentCode} — ${data.action}`);
});

onEvent("pos.commissions", async event => {
  const data = event.data as Record<string, unknown>;
  console.log(
    `[Dapr] Commission event: ${data.agentCode} — amount: ${data.amount}`
  );
});
