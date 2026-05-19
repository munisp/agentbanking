"""
Agent Scorecard — Kafka Consumer
Consumes platform events that trigger scorecard recomputation:
  - transaction.completed         → update transaction dimension
  - agent.kyc.updated             → update compliance dimension
  - agent.training.completed      → update training dimension
  - fraud.alert.raised            → update compliance dimension (fraud)
  - agent.commission.settled      → update network dimension
  - agent.finance.loan_disbursed  → update finance health
  - agent.finance.loan_repaid     → update finance health
"""
import json
import logging
import os
import signal
import threading
from typing import Dict, Any, Callable, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

from .topics import ScorecardTopics

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-broker-1:9092,kafka-broker-2:9092,kafka-broker-3:9092")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
KAFKA_SASL_MECHANISM    = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
KAFKA_SASL_USERNAME     = os.getenv("KAFKA_SASL_USERNAME", "scorecard-service")
KAFKA_SASL_PASSWORD     = os.getenv("KAFKA_SASL_PASSWORD", "")
KAFKA_SSL_CA_LOCATION   = os.getenv("KAFKA_SSL_CA_LOCATION", "/certs/ca.crt")
KAFKA_GROUP_ID          = os.getenv("KAFKA_SCORECARD_GROUP_ID", "agent-scorecard-consumer-group")


def _build_consumer_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": KAFKA_GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,          # Manual commit for at-least-once
        "max.poll.interval.ms": 300000,
        "session.timeout.ms": 30000,
        "heartbeat.interval.ms": 10000,
        "fetch.min.bytes": 1,
        "fetch.wait.max.ms": 500,
        "client.id": "agent-scorecard-consumer",
    }
    if KAFKA_SECURITY_PROTOCOL != "PLAINTEXT":
        cfg.update({
            "security.protocol": KAFKA_SECURITY_PROTOCOL,
            "sasl.mechanism": KAFKA_SASL_MECHANISM,
            "sasl.username": KAFKA_SASL_USERNAME,
            "sasl.password": KAFKA_SASL_PASSWORD,
        })
        if "SSL" in KAFKA_SECURITY_PROTOCOL:
            cfg["ssl.ca.location"] = KAFKA_SSL_CA_LOCATION
    return cfg


# ── Event Handlers ─────────────────────────────────────────────────────────────
class ScorecardEventHandlers:
    """
    Handles incoming Kafka events and triggers scorecard recomputation.
    Each handler receives the raw event dict and a DB session factory.
    """

    def __init__(self, db_session_factory: Callable):
        self.db_session_factory = db_session_factory

    def handle_transaction_completed(self, event: Dict[str, Any]):
        """
        When a transaction completes, queue a scorecard recomputation
        for the agent who processed it.
        """
        agent_id = event.get("agent_id")
        tenant_id = event.get("tenant_id")
        if not agent_id or not tenant_id:
            logger.warning("transaction.completed event missing agent_id/tenant_id: %s", event)
            return
        logger.info("Queuing scorecard recompute for agent=%s after transaction", agent_id)
        self._trigger_recompute(agent_id, tenant_id, trigger="transaction_completed")

    def handle_kyc_updated(self, event: Dict[str, Any]):
        """KYC status change → recompute compliance dimension."""
        agent_id = event.get("agent_id")
        tenant_id = event.get("tenant_id")
        if not agent_id:
            return
        logger.info("Queuing scorecard recompute for agent=%s after KYC update", agent_id)
        self._trigger_recompute(agent_id, tenant_id or "default", trigger="kyc_updated")

    def handle_training_completed(self, event: Dict[str, Any]):
        """Training module completion → recompute training dimension."""
        agent_id = event.get("agent_id")
        tenant_id = event.get("tenant_id")
        if not agent_id:
            return
        logger.info("Queuing scorecard recompute for agent=%s after training", agent_id)
        self._trigger_recompute(agent_id, tenant_id or "default", trigger="training_completed")

    def handle_fraud_alert(self, event: Dict[str, Any]):
        """Fraud alert → immediately recompute scorecard (compliance dimension)."""
        agent_id = event.get("agent_id")
        tenant_id = event.get("tenant_id")
        if not agent_id:
            return
        logger.warning("FRAUD ALERT received for agent=%s — triggering immediate recompute", agent_id)
        self._trigger_recompute(agent_id, tenant_id or "default", trigger="fraud_alert", priority="high")

    def handle_commission_settled(self, event: Dict[str, Any]):
        """Commission settlement → recompute network dimension."""
        agent_id = event.get("agent_id")
        tenant_id = event.get("tenant_id")
        if not agent_id:
            return
        self._trigger_recompute(agent_id, tenant_id or "default", trigger="commission_settled")

    def handle_loan_event(self, event: Dict[str, Any]):
        """Loan disbursement or repayment → recompute finance health in scorecard."""
        agent_id = event.get("agent_id")
        tenant_id = event.get("tenant_id")
        event_type = event.get("event_type", "loan_event")
        if not agent_id:
            return
        logger.info("Loan event '%s' for agent=%s — queuing recompute", event_type, agent_id)
        self._trigger_recompute(agent_id, tenant_id or "default", trigger=event_type)

    def _trigger_recompute(self, agent_id: str, tenant_id: str,
                           trigger: str, priority: str = "normal"):
        """
        Enqueue a scorecard recomputation job.
        In production this writes a recompute_request to the DB queue table
        which the Temporal workflow picks up.
        """
        try:
            with self.db_session_factory() as db:
                from sqlalchemy import text
                db.execute(
                    text("""
                        INSERT INTO scorecard_recompute_queue
                            (agent_id, tenant_id, trigger_reason, priority, queued_at)
                        VALUES
                            (:agent_id, :tenant_id, :trigger, :priority, NOW())
                        ON CONFLICT (agent_id, tenant_id)
                        DO UPDATE SET
                            trigger_reason = EXCLUDED.trigger_reason,
                            priority = EXCLUDED.priority,
                            queued_at = NOW()
                    """),
                    {"agent_id": agent_id, "tenant_id": tenant_id,
                     "trigger": trigger, "priority": priority}
                )
                db.commit()
        except Exception as e:
            logger.error("Failed to enqueue recompute for agent=%s: %s", agent_id, e)


# ── Consumer Loop ──────────────────────────────────────────────────────────────
class ScorecardKafkaConsumer:
    """
    Long-running Kafka consumer thread for the Agent Scorecard service.
    Subscribes to all relevant platform topics and dispatches to handlers.
    """

    TOPIC_HANDLER_MAP = {
        ScorecardTopics.TRANSACTION_COMPLETED:    "handle_transaction_completed",
        ScorecardTopics.AGENT_KYC_UPDATED:        "handle_kyc_updated",
        ScorecardTopics.AGENT_TRAINING_COMPLETED: "handle_training_completed",
        ScorecardTopics.FRAUD_ALERT_RAISED:       "handle_fraud_alert",
        ScorecardTopics.COMMISSION_SETTLED:       "handle_commission_settled",
        ScorecardTopics.LOAN_DISBURSED:           "handle_loan_event",
        ScorecardTopics.LOAN_REPAID:              "handle_loan_event",
    }

    def __init__(self, db_session_factory: Callable):
        self._consumer: Optional[Consumer] = None
        self._handlers = ScorecardEventHandlers(db_session_factory)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the consumer in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._consume_loop, daemon=True, name="scorecard-kafka-consumer")
        self._thread.start()
        logger.info("ScorecardKafkaConsumer started")

    def stop(self):
        """Gracefully stop the consumer."""
        self._running = False
        if self._consumer:
            self._consumer.close()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("ScorecardKafkaConsumer stopped")

    def _consume_loop(self):
        consumer = Consumer(_build_consumer_config())
        self._consumer = consumer
        topics = list(self.TOPIC_HANDLER_MAP.keys())
        consumer.subscribe(topics)
        logger.info("Subscribed to topics: %s", topics)

        try:
            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka consumer error: %s", msg.error())
                    continue

                topic = msg.topic()
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    handler_name = self.TOPIC_HANDLER_MAP.get(topic)
                    if handler_name:
                        handler = getattr(self._handlers, handler_name)
                        handler(payload)
                    consumer.commit(message=msg, asynchronous=False)
                except Exception as e:
                    logger.error("Error processing message from topic=%s: %s", topic, e)
                    # Do NOT commit on error — message will be reprocessed
        finally:
            consumer.close()
