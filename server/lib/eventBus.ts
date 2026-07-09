/**
 * Event Bus — async side effect processing
 *
 * Decouples business logic from side effects (notifications, analytics,
 * audit logging, cache invalidation). Events are processed asynchronously
 * and failures don't block the main request.
 */

type EventHandler = (payload: unknown) => Promise<void>;

interface EventDefinition {
  name: string;
  handlers: EventHandler[];
}

class EventBus {
  private events = new Map<string, EventHandler[]>();
  private deadLetterQueue: Array<{
    event: string;
    payload: unknown;
    error: string;
    timestamp: number;
  }> = [];

  on(event: string, handler: EventHandler) {
    const handlers = this.events.get(event) || [];
    handlers.push(handler);
    this.events.set(event, handlers);
  }

  async emit(event: string, payload: unknown) {
    const handlers = this.events.get(event) || [];
    // Fire-and-forget — don't await, don't block caller
    for (const handler of handlers) {
      handler(payload).catch(err => {
        this.deadLetterQueue.push({
          event,
          payload,
          error: err instanceof Error ? err.message : String(err),
          timestamp: Date.now(),
        });
        // Keep DLQ bounded
        if (this.deadLetterQueue.length > 10000) {
          this.deadLetterQueue = this.deadLetterQueue.slice(-5000);
        }
      });
    }
  }

  getDeadLetterQueue() {
    return this.deadLetterQueue.slice(-100);
  }

  getRegisteredEvents(): string[] {
    return Array.from(this.events.keys());
  }
}

export const eventBus = new EventBus();

// ── Built-in event types ────────────────────────────────────────────────────
export const EVENTS = {
  // Transaction events
  TRANSACTION_CREATED: "transaction.created",
  TRANSACTION_COMPLETED: "transaction.completed",
  TRANSACTION_FAILED: "transaction.failed",
  TRANSACTION_REVERSED: "transaction.reversed",

  // Agent events
  AGENT_REGISTERED: "agent.registered",
  AGENT_STATUS_CHANGED: "agent.status_changed",
  AGENT_FLOAT_LOW: "agent.float_low",
  AGENT_FLOAT_DEPLETED: "agent.float_depleted",

  // KYC events
  KYC_SUBMITTED: "kyc.submitted",
  KYC_APPROVED: "kyc.approved",
  KYC_REJECTED: "kyc.rejected",
  KYC_EXPIRED: "kyc.expired",

  // POS events
  TERMINAL_PROVISIONED: "terminal.provisioned",
  TERMINAL_HEARTBEAT_MISSED: "terminal.heartbeat_missed",
  TERMINAL_FIRMWARE_UPDATED: "terminal.firmware_updated",

  // Settlement events
  SETTLEMENT_BATCH_CREATED: "settlement.batch_created",
  SETTLEMENT_COMPLETED: "settlement.completed",

  // Security events
  LOGIN_FAILED: "security.login_failed",
  SUSPICIOUS_ACTIVITY: "security.suspicious_activity",
  FRAUD_DETECTED: "security.fraud_detected",

  // System events
  CACHE_INVALIDATED: "system.cache_invalidated",
  NOTIFICATION_SENT: "system.notification_sent",
} as const;
