from confluent_kafka import Producer
import json
import time
import threading
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import defaultdict


logger = logging.getLogger(__name__)


class AdminTopics:
    ADMIN = "admin.lifecycle"
    USERS = "admin.users"
    KYC = "admin.kyc"
    AUTH = "admin.auth"
    PROFILE = "admin.profile"
    AUDIT = "admin.audit"
    NOTIFICATION = "admin.notification"


class AdminEventTypes:
    # User lifecycle events
    ADMIN_CREATED = "admin.created"
    ADMIN_UPDATED = "admin.updated"
    ADMIN_DELETED = "admin.deleted"

    # Authentication events
    ADMIN_SIGNUP = "admin.signup"
    ADMIN_LOGIN = "admin.login"
    ADMIN_LOGOUT = "admin.logout"

    # KYC events
    KYC_STARTED = "admin.kyc.started"
    KYC_SAVED = "admin.kyc.saved"
    KYC_COMPLETED = "admin.kyc.completed"
    KYC_VERIFIED = "admin.kyc.verified"
    KYC_FAILED = "admin.kyc.failed"

    # Status change events
    ADMIN_ACTIVATED = "admin.activated"
    ADMIN_DEACTIVATED = "admin.deactivated"
    ADMIN_SUSPENDED = "admin.suspended"

    # Profile events
    PROFILE_UPDATED = "admin.profile.updated"
    PROFILE_VIEWED = "admin.profile.viewed"

    # Audit events
    AUDIT_ACTION = "admin.audit.action"


class BufferedEvent:

    def __init__(self, topic: str, event: Dict[str, Any], created_at: float):
        self.topic = topic
        self.event = event
        self.created_at = created_at


class KafkaMetrics:

    def __init__(self):
        self.messages_published = defaultdict(lambda: defaultdict(int))
        self.publish_latencies = defaultdict(list)
        self.lock = threading.Lock()

    def inc_messages_published(self, topic: str, status: str):
        with self.lock:
            self.messages_published[topic][status] += 1

    def observe_latency(self, topic: str, latency: float):
        with self.lock:
            self.publish_latencies[topic].append(latency)
            # Keep only last 1000 measurements
            if len(self.publish_latencies[topic]) > 1000:
                self.publish_latencies[topic] = self.publish_latencies[topic][-1000:]

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
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
    def __init__(
        self,
        config: Dict[str, str],
        buffer_size: int = 100,
        flush_interval: float = 5.0,
    ):
        """
        Initialize Kafka client with buffering and metrics

        Args:
            config: Kafka configuration dictionary
            buffer_size: Maximum events to buffer before flushing
            flush_interval: Seconds between automatic flushes
        """
        self.producer = Producer(config)
        self.config = config
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # Event buffering
        self.event_buffer: List[BufferedEvent] = []
        self.buffer_lock = threading.Lock()

        # Metrics
        self.metrics = KafkaMetrics()

        # Background flusher
        self.connected = True
        self.flusher_thread = threading.Thread(
            target=self._background_flusher, daemon=True
        )
        self.flusher_thread.start()

        logger.info(
            f"Kafka client initialized with brokers: {config.get('bootstrap.servers')}"
        )

    def delivery_report(self, err, msg):
        """Called once for each message produced to indicate delivery result."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
            self.metrics.inc_messages_published(msg.topic(), "error")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")
            self.metrics.inc_messages_published(msg.topic(), "success")

    def publish_event(
        self, topic: str, event: Dict[str, Any], key: Optional[str] = None
    ) -> bool:
        """
        Publish an event to Kafka

        Args:
            topic: Kafka topic
            event: Event dictionary
            key: Optional message key

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()

        try:
            # Ensure correlation_id exists
            if "correlation_id" not in event:
                import uuid

                event["correlation_id"] = f"corr-{uuid.uuid4()}"

            # Ensure timestamp exists
            if "timestamp" not in event:
                event["timestamp"] = datetime.utcnow().isoformat()

            # Serialize event with UUID handling
            import uuid

            def default_serializer(obj):
                if isinstance(obj, uuid.UUID):
                    return str(obj)
                raise TypeError(f"Type {type(obj)} not serializable")

            payload = json.dumps(event, default=default_serializer)

            # Produce to Kafka
            self.producer.produce(
                topic,
                key=key.encode("utf-8") if key else None,
                value=payload.encode("utf-8"),
                callback=self.delivery_report,
            )

            # Trigger delivery callbacks
            self.producer.poll(0)

            # Record metrics
            latency = time.time() - start_time
            self.metrics.observe_latency(topic, latency)

            logger.info(f"Published event to {topic}: {event.get('type', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish event to {topic}: {e}")
            self.metrics.inc_messages_published(topic, "error")
            return False

    def publish_event_async(
        self, topic: str, event: Dict[str, Any], key: Optional[str] = None
    ):
        """Publish event asynchronously in a separate thread"""
        thread = threading.Thread(
            target=self.publish_event, args=(topic, event, key), daemon=True
        )
        thread.start()

    def publish_batch(self, topic: str, events: List[Dict[str, Any]]) -> int:
        """
        Publish multiple events to a topic

        Returns:
            Number of successfully published events
        """
        success_count = 0
        for event in events:
            if self.publish_event(topic, event):
                success_count += 1
        return success_count

    def buffer_event(self, topic: str, event: Dict[str, Any]):
        """Add event to buffer for later publishing"""
        with self.buffer_lock:
            self.event_buffer.append(BufferedEvent(topic, event, time.time()))

            # Flush if buffer is full
            if len(self.event_buffer) >= self.buffer_size:
                self._flush_buffer()

    def _background_flusher(self):
        """Background thread that periodically flushes the event buffer"""
        while self.connected:
            time.sleep(self.flush_interval)
            with self.buffer_lock:
                if self.event_buffer:
                    self._flush_buffer()

    def _flush_buffer(self):
        """Flush buffered events (must be called with buffer_lock held)"""
        if not self.event_buffer:
            return

        logger.info(f"Flushing {len(self.event_buffer)} buffered events")

        for buffered in self.event_buffer:
            self.publish_event(buffered.topic, buffered.event)

        self.event_buffer.clear()

    def flush(self, timeout: float = 10.0):
        """
        Wait for all messages in the producer queue to be delivered

        Args:
            timeout: Maximum time to wait in seconds
        """
        # First flush any buffered events
        with self.buffer_lock:
            self._flush_buffer()

        # Then flush the producer queue
        remaining = self.producer.flush(timeout)
        if remaining > 0:
            logger.warning(f"{remaining} messages were not delivered")

    def close(self):
        """Close the Kafka client and flush all pending messages"""
        logger.info("Closing Kafka client")
        self.connected = False
        self.flush()
        logger.info("Kafka client closed")

    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.connected

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.get_stats()

    # Helper methods for user events
    def publish_user_event(
        self,
        event_type: str,
        user_id: str,
        tenant_id: str,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Publish a user lifecycle event"""
        event = {
            "type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        return self.publish_event(AdminTopics.USERS, event, key=str(user_id))

    def publish_kyc_event(
        self,
        event_type: str,
        user_id: str,
        tenant_id: str,
        kyc_status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Publish a KYC event"""
        event = {
            "type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "kyc_status": kyc_status,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        return self.publish_event(AdminTopics.KYC, event, key=str(user_id))

    def publish_auth_event(
        self,
        event_type: str,
        user_id: str,
        tenant_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Publish an authentication event"""
        event = {
            "type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        return self.publish_event(AdminTopics.AUTH, event, key=user_id)

    def publish_audit_event(
        self,
        user_id: str,
        tenant_id: str,
        action: str,
        actor: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Publish an audit event"""
        event = {
            "type": AdminEventTypes.AUDIT_ACTION,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "action": action,
            "actor": actor,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {"details": details or {}},
        }
        return self.publish_event(AdminTopics.AUDIT, event, key=user_id)
