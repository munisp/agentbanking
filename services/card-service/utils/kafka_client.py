import json
import time
import threading
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import defaultdict

try:
    from confluent_kafka import Producer  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Producer = None

logger = logging.getLogger(__name__)

class CardTopics:
    CARD = "card.lifecycle"
    NOTIFICATION = "card.notification"

class CardEventTypes:
    CARD_ISSUED = "card.issued"
    CARD_BLOCKED = "card.blocked"
    CARD_ACTIVATED = "card.activated"
    CARD_DEACTIVATED = "card.deactivated"
    CARD_LOST = "card.lost"
    CARD_REPLACED = "card.replaced"

class BufferedEvent:
    def __init__(self, topic: str, event: Dict[str, Any], created_at: float):
        self.topic = topic
        self.event = event
        self.created_at = created_at

class KafkaMetrics:
    def __init__(self):
        self.messages_published = defaultdict(lambda: defaultdict(int))
        self.publish_latencies = defaultdict(list)
        self._lock = threading.Lock()

    def inc_messages_published(self, topic: str, status: str):
        with self._lock:
            self.messages_published[topic][status] += 1

    def observe_latency(self, topic: str, latency: float):
        with self._lock:
            self.publish_latencies[topic].append(latency)
            if len(self.publish_latencies[topic]) > 1000:
                self.publish_latencies[topic] = self.publish_latencies[topic][-1000:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = {
                "messages_published": dict(self.messages_published),
                "latencies": {},
            }
            for topic, latencies in self.publish_latencies.items():
                if latencies:
                    stats["latencies"][topic] = {
                        "avg": sum(latencies) / len(latencies),
                        "min": min(latencies),
                        "max": max(latencies),
                        "count": len(latencies),
                    }
            return stats

class KafkaClient:
    def __init__(self, config: Dict[str, str], buffer_size: int = 100, flush_interval: float = 5.0):
        self.producer = Producer(config) if Producer is not None else None
        self.config = config
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.event_buffer: List[BufferedEvent] = []
        self.buffer_lock = threading.Lock()
        self.metrics = KafkaMetrics()
        self.connected = self.producer is not None
        self.flusher_thread = None

        if self.producer is not None:
            self.flusher_thread = threading.Thread(
                target=self._background_flusher, daemon=True
            )
            self.flusher_thread.start()
            logger.info(
                f"Kafka client initialized with brokers: {config.get('bootstrap.servers')}"
            )
        else:
            logger.warning(
                "Kafka producer unavailable; event publishing will be disabled"
            )

    def delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
            self.metrics.inc_messages_published(msg.topic(), "error")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")
            self.metrics.inc_messages_published(msg.topic(), "success")

    def publish_event(self, topic: str, event: Dict[str, Any], key: Optional[str] = None) -> bool:
        start_time = time.time()
        try:
            if self.producer is None:
                logger.warning(f"Skipping publish to {topic}: Kafka producer unavailable")
                self.metrics.inc_messages_published(topic, "disabled")
                return False

            if "correlation_id" not in event:
                import uuid
                event["correlation_id"] = f"corr-{uuid.uuid4()}"
            if "timestamp" not in event:
                event["timestamp"] = datetime.utcnow().isoformat()
            import uuid
            def default_serializer(obj):
                if isinstance(obj, uuid.UUID):
                    return str(obj)
                raise TypeError(f"Type {type(obj)} not serializable")
            payload = json.dumps(event, default=default_serializer)
            self.producer.produce(
                topic,
                key=key.encode("utf-8") if key else None,
                value=payload.encode("utf-8"),
                callback=self.delivery_report,
            )
            self.producer.poll(0)
            latency = time.time() - start_time
            self.metrics.observe_latency(topic, latency)
            logger.info(f"Published event to {topic}: {event.get('type', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event to {topic}: {e}")
            self.metrics.inc_messages_published(topic, "error")
            return False

    def publish_event_async(self, topic: str, event: Dict[str, Any], key: Optional[str] = None):
        thread = threading.Thread(target=self.publish_event, args=(topic, event, key), daemon=True)
        thread.start()

    def publish_batch(self, topic: str, events: List[Dict[str, Any]]) -> int:
        success_count = 0
        for event in events:
            if self.publish_event(topic, event):
                success_count += 1
        return success_count

    def buffer_event(self, topic: str, event: Dict[str, Any]):
        with self.buffer_lock:
            self.event_buffer.append(BufferedEvent(topic, event, time.time()))
            if len(self.event_buffer) >= self.buffer_size:
                self._flush_buffer()

    def _background_flusher(self):
        while self.connected:
            time.sleep(self.flush_interval)
            with self.buffer_lock:
                if self.event_buffer:
                    self._flush_buffer()

    def _flush_buffer(self):
        if not self.event_buffer:
            return
        logger.info(f"Flushing {len(self.event_buffer)} buffered events")
        for buffered in self.event_buffer:
            self.publish_event(buffered.topic, buffered.event)
        self.event_buffer.clear()

    def flush(self, timeout: float = 10.0):
        if self.producer is None:
            return 0

        with self.buffer_lock:
            self._flush_buffer()
        remaining = self.producer.flush(timeout)
        if remaining > 0:
            logger.warning(f"{remaining} messages were not delivered")

    def close(self):
        logger.info("Closing Kafka client")
        self.connected = False
        self.flush()
        logger.info("Kafka client closed")

    def is_connected(self) -> bool:
        return self.connected

    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.get_stats()

    def publish_card_event(self, event_type: str, card_id: str, tenant_id: str, status: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        event = {
            "type": event_type,
            "card_id": card_id,
            "tenant_id": tenant_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        return self.publish_event(CardTopics.CARD, event, key=str(card_id))
