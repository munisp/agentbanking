"""
Agent Scorecard — Kafka Producer
Publishes scorecard events to Kafka topics using the platform's
confluent_kafka pattern with exactly-once semantics.
"""
import json
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime

from confluent_kafka import Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from .topics import ScorecardTopics, ScorecardComputedEvent, TierChangedEvent

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-broker-1:9092,kafka-broker-2:9092,kafka-broker-3:9092")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
KAFKA_SASL_MECHANISM    = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
KAFKA_SASL_USERNAME     = os.getenv("KAFKA_SASL_USERNAME", "scorecard-service")
KAFKA_SASL_PASSWORD     = os.getenv("KAFKA_SASL_PASSWORD", "")
KAFKA_SSL_CA_LOCATION   = os.getenv("KAFKA_SSL_CA_LOCATION", "/certs/ca.crt")


def _build_producer_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "acks": "all",
        "enable.idempotence": True,
        "max.in.flight.requests.per.connection": 5,
        "retries": 2147483647,
        "retry.backoff.ms": 500,
        "compression.type": "snappy",
        "linger.ms": 5,
        "batch.size": 65536,
        "client.id": "agent-scorecard-producer",
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


class ScorecardKafkaProducer:
    """
    Thread-safe Kafka producer for Agent Scorecard events.
    Uses confluent_kafka with exactly-once semantics and Avro-compatible JSON payloads.
    """

    def __init__(self):
        self._producer: Optional[Producer] = None
        self._messages_sent = 0
        self._messages_failed = 0

    def _get_producer(self) -> Producer:
        if self._producer is None:
            self._producer = Producer(_build_producer_config())
            logger.info("ScorecardKafkaProducer initialized")
        return self._producer

    def _delivery_callback(self, err, msg):
        if err:
            self._messages_failed += 1
            logger.error(
                "Kafka delivery failed | topic=%s partition=%s offset=%s error=%s",
                msg.topic(), msg.partition(), msg.offset(), err
            )
        else:
            self._messages_sent += 1
            logger.debug(
                "Kafka delivery OK | topic=%s partition=%s offset=%s",
                msg.topic(), msg.partition(), msg.offset()
            )

    def _publish(self, topic: str, payload: Dict[str, Any], key: Optional[str] = None) -> bool:
        try:
            producer = self._get_producer()
            producer.produce(
                topic=topic,
                key=key.encode("utf-8") if key else None,
                value=json.dumps(payload).encode("utf-8"),
                headers={
                    "content-type": "application/json",
                    "source-service": "agent-scorecard",
                    "event-time": datetime.utcnow().isoformat(),
                },
                callback=self._delivery_callback,
            )
            producer.poll(0)  # Trigger delivery callbacks
            return True
        except KafkaException as e:
            logger.error("Kafka publish error | topic=%s error=%s", topic, e)
            return False

    def publish_scorecard_computed(self, event: ScorecardComputedEvent) -> bool:
        """Publish a ScorecardComputedEvent to Kafka."""
        return self._publish(
            topic=ScorecardTopics.SCORECARD_COMPUTED,
            payload=event.to_dict(),
            key=event.agent_id,
        )

    def publish_tier_changed(self, event: TierChangedEvent) -> bool:
        """Publish a TierChangedEvent to Kafka when an agent's tier changes."""
        return self._publish(
            topic=ScorecardTopics.SCORECARD_TIER_CHANGED,
            payload=event.to_dict(),
            key=event.agent_id,
        )

    def publish_leaderboard_updated(self, tenant_id: str, leaderboard: list) -> bool:
        """Publish a leaderboard snapshot to Kafka."""
        payload = {
            "event_id": __import__("uuid").uuid4().__str__(),
            "event_type": ScorecardTopics.LEADERBOARD_UPDATED,
            "tenant_id": tenant_id,
            "leaderboard": leaderboard,
            "updated_at": datetime.utcnow().isoformat(),
            "source_service": "agent-scorecard",
        }
        return self._publish(
            topic=ScorecardTopics.LEADERBOARD_UPDATED,
            payload=payload,
            key=tenant_id,
        )

    def flush(self, timeout: float = 10.0):
        """Flush all pending messages."""
        if self._producer:
            remaining = self._producer.flush(timeout=timeout)
            if remaining > 0:
                logger.warning("Kafka flush: %d messages still in queue after timeout", remaining)

    def stats(self) -> Dict[str, int]:
        return {"sent": self._messages_sent, "failed": self._messages_failed}


# ── Singleton ──────────────────────────────────────────────────────────────────
_producer_instance: Optional[ScorecardKafkaProducer] = None


def get_scorecard_kafka_producer() -> ScorecardKafkaProducer:
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = ScorecardKafkaProducer()
    return _producer_instance
