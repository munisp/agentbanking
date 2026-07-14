"""
Shared Kafka producer/consumer base classes for all competitor-gap services.
Uses confluent-kafka for production-grade reliability.
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-cluster-kafka-bootstrap:9092")
KAFKA_SECURITY  = os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
KAFKA_SASL_MECH = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
KAFKA_USERNAME  = os.getenv("KAFKA_USERNAME", "")
KAFKA_PASSWORD  = os.getenv("KAFKA_PASSWORD", "")


def _build_producer_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "acks": "all",
        "retries": 5,
        "retry.backoff.ms": 300,
        "enable.idempotence": True,
        "compression.type": "snappy",
        "linger.ms": 5,
        "batch.size": 65536,
    }
    if KAFKA_USERNAME:
        cfg.update({
            "security.protocol": KAFKA_SECURITY,
            "sasl.mechanism": KAFKA_SASL_MECH,
            "sasl.username": KAFKA_USERNAME,
            "sasl.password": KAFKA_PASSWORD,
        })
    return cfg


def _build_consumer_config(group_id: str) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 300000,
        "session.timeout.ms": 30000,
    }
    if KAFKA_USERNAME:
        cfg.update({
            "security.protocol": KAFKA_SECURITY,
            "sasl.mechanism": KAFKA_SASL_MECH,
            "sasl.username": KAFKA_USERNAME,
            "sasl.password": KAFKA_PASSWORD,
        })
    return cfg


class BaseKafkaProducer:
    """Thread-safe Kafka producer base class."""

    def __init__(self, service_name: str):
        self._service = service_name
        self._producer = None
        self._sent = 0
        self._failed = 0

    def _get_producer(self):
        if self._producer is None:
            try:
                from confluent_kafka import Producer
                self._producer = Producer(_build_producer_config())
                logger.info("[%s] Kafka producer connected to %s", self._service, KAFKA_BOOTSTRAP)
            except Exception as exc:
                logger.error("[%s] Kafka producer init failed: %s", self._service, exc)
        return self._producer

    def _delivery_report(self, err, msg):
        if err:
            self._failed += 1
            logger.error("[%s] Kafka delivery failed topic=%s err=%s", self._service, msg.topic(), err)
        else:
            self._sent += 1

    def publish(self, topic: str, payload: Dict[str, Any], key: Optional[str] = None) -> bool:
        producer = self._get_producer()
        if not producer:
            return False
        envelope = {
            "event_id": str(uuid.uuid4()),
            "source_service": self._service,
            "timestamp": datetime.utcnow().isoformat(),
            **payload,
        }
        try:
            producer.produce(
                topic=topic,
                value=json.dumps(envelope).encode("utf-8"),
                key=(key or str(uuid.uuid4())).encode("utf-8"),
                on_delivery=self._delivery_report,
            )
            producer.poll(0)
            return True
        except Exception as exc:
            self._failed += 1
            logger.error("[%s] Kafka publish error topic=%s: %s", self._service, topic, exc)
            return False

    def flush(self, timeout: float = 10.0):
        p = self._get_producer()
        if p:
            remaining = p.flush(timeout=timeout)
            if remaining:
                logger.warning("[%s] %d messages still queued after flush", self._service, remaining)

    @property
    def stats(self) -> Dict[str, int]:
        return {"sent": self._sent, "failed": self._failed}


class BaseKafkaConsumer:
    """Blocking Kafka consumer base class with manual commit."""

    def __init__(self, service_name: str, topics: list, group_id: str):
        self._service = service_name
        self._topics = topics
        self._group_id = group_id
        self._consumer = None
        self._running = False

    def _get_consumer(self):
        if self._consumer is None:
            try:
                from confluent_kafka import Consumer
                self._consumer = Consumer(_build_consumer_config(self._group_id))
                self._consumer.subscribe(self._topics)
                logger.info("[%s] Kafka consumer subscribed to %s", self._service, self._topics)
            except Exception as exc:
                logger.error("[%s] Kafka consumer init failed: %s", self._service, exc)
        return self._consumer

    def start(self, handler: Callable[[str, Dict[str, Any]], None]):
        """Start consuming messages. Calls handler(topic, payload) for each message."""
        self._running = True
        consumer = self._get_consumer()
        if not consumer:
            logger.error("[%s] Cannot start consumer — no connection", self._service)
            return
        logger.info("[%s] Kafka consumer loop started", self._service)
        try:
            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.warning("[%s] Consumer error: %s", self._service, msg.error())
                    continue
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    handler(msg.topic(), payload)
                    consumer.commit(message=msg, asynchronous=False)
                except Exception as exc:
                    logger.error("[%s] Handler error topic=%s: %s", self._service, msg.topic(), exc)
        finally:
            consumer.close()
            logger.info("[%s] Kafka consumer stopped", self._service)

    def stop(self):
        self._running = False
