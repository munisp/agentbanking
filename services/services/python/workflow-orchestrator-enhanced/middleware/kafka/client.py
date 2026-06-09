"""
Kafka client for workflow event streaming
"""
import json
import logging
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime

from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


class KafkaConfig:
    """Kafka configuration"""
    def __init__(
        self,
        brokers: List[str],
        topic_workflow_events: str = "workflow-events",
        topic_workflow_tasks: str = "workflow-tasks",
        consumer_group: str = "workflow-orchestrator",
        enable_auto_commit: bool = True,
        session_timeout_ms: int = 30000,
        max_poll_interval_ms: int = 300000,
    ):
        self.brokers = brokers
        self.topic_workflow_events = topic_workflow_events
        self.topic_workflow_tasks = topic_workflow_tasks
        self.consumer_group = consumer_group
        self.enable_auto_commit = enable_auto_commit
        self.session_timeout_ms = session_timeout_ms
        self.max_poll_interval_ms = max_poll_interval_ms


class WorkflowEvent:
    """Workflow lifecycle event"""
    def __init__(
        self,
        event_id: str,
        event_type: str,
        workflow_id: str,
        workflow_type: str,
        status: str,
        tenant_id: str,
        user_id: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.status = status
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "status": self.status,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "data": self.data,
        }


class KafkaClient:
    """Kafka client for workflow orchestration"""

    def __init__(self, config: KafkaConfig):
        self.config = config
        
        # Create producer
        self.producer = Producer({
            "bootstrap.servers": ",".join(config.brokers),
            "acks": "all",
            "retries": 3,
            "max.in.flight.requests.per.connection": 5,
            "compression.type": "snappy",
            "linger.ms": 10,
            "batch.size": 16384,
        })

        # Create consumer
        self.consumer = Consumer({
            "bootstrap.servers": ",".join(config.brokers),
            "group.id": config.consumer_group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": config.enable_auto_commit,
            "session.timeout.ms": config.session_timeout_ms,
            "max.poll.interval.ms": config.max_poll_interval_ms,
        })

    def publish_workflow_event(self, event: WorkflowEvent) -> None:
        """Publish a workflow lifecycle event to Kafka"""
        logger.info(
            f"Publishing workflow event to Kafka: {event.workflow_id} - {event.event_type}"
        )

        # Serialize event to JSON
        data = json.dumps(event.to_dict()).encode("utf-8")

        # Produce message
        self.producer.produce(
            topic=self.config.topic_workflow_events,
            key=event.workflow_id.encode("utf-8"),
            value=data,
            headers=[
                ("event_type", event.event_type.encode("utf-8")),
                ("workflow_type", event.workflow_type.encode("utf-8")),
            ],
            callback=self._delivery_callback,
        )

        # Flush to ensure delivery
        self.producer.poll(0)

    def publish_workflow_task(self, task: Dict[str, Any]) -> None:
        """Publish a workflow task to Kafka for asynchronous processing"""
        logger.info(f"Publishing workflow task to Kafka")

        # Serialize task to JSON
        data = json.dumps(task).encode("utf-8")

        # Produce message
        self.producer.produce(
            topic=self.config.topic_workflow_tasks,
            value=data,
            callback=self._delivery_callback,
        )

        # Flush to ensure delivery
        self.producer.poll(0)

    def consume_workflow_events(
        self, handler: Callable[[WorkflowEvent], None]
    ) -> None:
        """Consume workflow events from Kafka"""
        logger.info(
            f"Starting to consume workflow events from Kafka: {self.config.topic_workflow_events}"
        )

        # Subscribe to topic
        self.consumer.subscribe([self.config.topic_workflow_events])

        try:
            while True:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        continue

                # Parse event
                try:
                    event_data = json.loads(msg.value().decode("utf-8"))
                    event = WorkflowEvent(
                        event_id=event_data["event_id"],
                        event_type=event_data["event_type"],
                        workflow_id=event_data["workflow_id"],
                        workflow_type=event_data["workflow_type"],
                        status=event_data["status"],
                        tenant_id=event_data["tenant_id"],
                        user_id=event_data["user_id"],
                        data=event_data["data"],
                        timestamp=datetime.fromisoformat(event_data["timestamp"]),
                    )

                    # Handle event
                    handler(event)

                    # Commit offset if auto-commit is disabled
                    if not self.config.enable_auto_commit:
                        self.consumer.commit(asynchronous=False)

                except Exception as e:
                    logger.error(f"Failed to process event: {e}")
                    continue

        except KeyboardInterrupt:
            logger.info("Consumer interrupted")
        finally:
            self.consumer.close()

    def flush(self, timeout: float = 10.0) -> int:
        """Flush any pending messages in the producer"""
        remaining = self.producer.flush(timeout=timeout)
        if remaining > 0:
            logger.warning(f"Failed to flush all messages: {remaining} remaining")
        return remaining

    def close(self) -> None:
        """Close the Kafka client"""
        self.flush()
        self.consumer.close()

    def _delivery_callback(self, err, msg):
        """Callback for message delivery reports"""
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
            )


class KafkaAdmin:
    """Kafka admin client for topic management"""

    def __init__(self, brokers: List[str]):
        self.admin = AdminClient({"bootstrap.servers": ",".join(brokers)})

    def create_topic(
        self, topic: str, num_partitions: int = 3, replication_factor: int = 3
    ) -> None:
        """Create a Kafka topic"""
        logger.info(f"Creating Kafka topic: {topic}")

        new_topic = NewTopic(
            topic, num_partitions=num_partitions, replication_factor=replication_factor
        )

        fs = self.admin.create_topics([new_topic])

        for topic, f in fs.items():
            try:
                f.result()
                logger.info(f"Topic {topic} created successfully")
            except Exception as e:
                logger.error(f"Failed to create topic {topic}: {e}")

    def delete_topic(self, topic: str) -> None:
        """Delete a Kafka topic"""
        logger.info(f"Deleting Kafka topic: {topic}")

        fs = self.admin.delete_topics([topic])

        for topic, f in fs.items():
            try:
                f.result()
                logger.info(f"Topic {topic} deleted successfully")
            except Exception as e:
                logger.error(f"Failed to delete topic {topic}: {e}")

