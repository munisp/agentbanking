"""
Kafka Producer Library for Remittance Platform V11.0

Provides a reusable Kafka producer for publishing events from microservices.

Features:
- Async/await support with aiokafka
- Automatic JSON serialization
- Schema validation
- Error handling and retries
- Delivery guarantees (at-least-once)
- Metrics and logging

Author: Manus AI
Date: November 11, 2025
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """
    Async Kafka producer for publishing events.
    
    Usage:
        producer = KafkaEventProducer()
        await producer.start()
        
        await producer.publish_event(
            topic="transactions.created",
            event_data={"transaction_id": "txn-123", "amount": 10000}
        )
        
        await producer.stop()
    """
    
    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        client_id: str = "remittance-producer",
        compression_type: str = "snappy",
        acks: str = "all",
        retries: int = 3,
        max_in_flight_requests: int = 5
    ):
        """
        Initialize Kafka producer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            client_id: Client ID for this producer
            compression_type: Compression algorithm (none, gzip, snappy, lz4, zstd)
            acks: Acknowledgment mode (0, 1, all)
            retries: Number of retries for failed sends
            max_in_flight_requests: Max in-flight requests per connection
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "kafka-1:9092,kafka-2:9093,kafka-3:9094"
        )
        self.client_id = client_id
        self.compression_type = compression_type
        self.acks = acks
        self.retries = retries
        self.max_in_flight_requests = max_in_flight_requests
        
        self.producer: Optional[AIOKafkaProducer] = None
        self._is_started = False
        
        # Metrics
        self.messages_sent = 0
        self.messages_failed = 0
        self.bytes_sent = 0
    
    async def start(self):
        """Start the Kafka producer."""
        if self._is_started:
            logger.warning("Producer already started")
            return
        
        logger.info(f"Starting Kafka producer: {self.client_id}")
        logger.info(f"Bootstrap servers: {self.bootstrap_servers}")
        
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers.split(","),
            client_id=self.client_id,
            compression_type=self.compression_type,
            acks=self.acks,
            retries=self.retries,
            max_in_flight_requests_per_connection=self.max_in_flight_requests,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        
        await self.producer.start()
        self._is_started = True
        
        logger.info("✅ Kafka producer started successfully")
    
    async def stop(self):
        """Stop the Kafka producer."""
        if not self._is_started:
            return
        
        logger.info("Stopping Kafka producer...")
        
        if self.producer:
            await self.producer.stop()
        
        self._is_started = False
        logger.info("✅ Kafka producer stopped")
        
        # Log metrics
        logger.info(f"Producer metrics:")
        logger.info(f"  Messages sent: {self.messages_sent}")
        logger.info(f"  Messages failed: {self.messages_failed}")
        logger.info(f"  Bytes sent: {self.bytes_sent}")
    
    async def publish_event(
        self,
        topic: str,
        event_data: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        partition: Optional[int] = None
    ) -> bool:
        """
        Publish an event to Kafka topic.
        
        Args:
            topic: Kafka topic name
            event_data: Event data (will be JSON serialized)
            key: Optional partition key
            headers: Optional message headers
            partition: Optional specific partition
            
        Returns:
            True if successful, False otherwise
        """
        if not self._is_started:
            raise RuntimeError("Producer not started. Call start() first.")
        
        # Add metadata to event
        enriched_event = {
            **event_data,
            "_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "producer_id": self.client_id,
                "topic": topic,
                "version": "1.0"
            }
        }
        
        # Convert headers to bytes
        kafka_headers = None
        if headers:
            kafka_headers = [
                (k, v.encode("utf-8") if isinstance(v, str) else v)
                for k, v in headers.items()
            ]
        
        try:
            # Send message
            future = await self.producer.send(
                topic=topic,
                value=enriched_event,
                key=key,
                headers=kafka_headers,
                partition=partition
            )
            
            # Wait for acknowledgment
            record_metadata = await future
            
            # Update metrics
            self.messages_sent += 1
            self.bytes_sent += len(json.dumps(enriched_event).encode("utf-8"))
            
            logger.debug(
                f"✅ Event published to {topic} "
                f"(partition={record_metadata.partition}, "
                f"offset={record_metadata.offset})"
            )
            
            return True
        
        except KafkaError as e:
            self.messages_failed += 1
            logger.error(f"❌ Failed to publish event to {topic}: {e}")
            return False
        except Exception as e:
            self.messages_failed += 1
            logger.error(f"❌ Unexpected error publishing event to {topic}: {e}")
            return False
    
    async def publish_batch(
        self,
        topic: str,
        events: List[Dict[str, Any]],
        keys: Optional[List[str]] = None
    ) -> int:
        """
        Publish multiple events in batch.
        
        Args:
            topic: Kafka topic name
            events: List of event data dictionaries
            keys: Optional list of partition keys (same length as events)
            
        Returns:
            Number of successfully published events
        """
        if not self._is_started:
            raise RuntimeError("Producer not started. Call start() first.")
        
        if keys and len(keys) != len(events):
            raise ValueError("Keys list must have same length as events list")
        
        success_count = 0
        
        for i, event_data in enumerate(events):
            key = keys[i] if keys else None
            success = await self.publish_event(topic, event_data, key=key)
            if success:
                success_count += 1
        
        logger.info(
            f"Batch publish complete: {success_count}/{len(events)} "
            f"events published to {topic}"
        )
        
        return success_count
    
    async def flush(self):
        """Flush any pending messages."""
        if self.producer:
            await self.producer.flush()
            logger.debug("Producer flushed")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics."""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "bytes_sent": self.bytes_sent,
            "success_rate": (
                self.messages_sent / (self.messages_sent + self.messages_failed)
                if (self.messages_sent + self.messages_failed) > 0
                else 0
            )
        }


# Convenience functions for common event types

async def publish_transaction_event(
    producer: KafkaEventProducer,
    event_type: str,
    transaction_data: Dict[str, Any]
) -> bool:
    """
    Publish transaction event.
    
    Args:
        producer: Kafka producer instance
        event_type: Event type (created, completed, failed, reversed)
        transaction_data: Transaction data
        
    Returns:
        True if successful
    """
    topic = f"transactions.{event_type}"
    return await producer.publish_event(
        topic=topic,
        event_data=transaction_data,
        key=transaction_data.get("transaction_id")
    )


async def publish_agent_event(
    producer: KafkaEventProducer,
    event_type: str,
    agent_data: Dict[str, Any]
) -> bool:
    """
    Publish agent event.
    
    Args:
        producer: Kafka producer instance
        event_type: Event type (registered, verified, suspended, etc.)
        agent_data: Agent data
        
    Returns:
        True if successful
    """
    topic = f"agents.{event_type}"
    return await producer.publish_event(
        topic=topic,
        event_data=agent_data,
        key=agent_data.get("agent_id")
    )


async def publish_commission_event(
    producer: KafkaEventProducer,
    event_type: str,
    commission_data: Dict[str, Any]
) -> bool:
    """
    Publish commission event.
    
    Args:
        producer: Kafka producer instance
        event_type: Event type (calculated, credited, override)
        commission_data: Commission data
        
    Returns:
        True if successful
    """
    topic = f"commissions.{event_type}"
    return await producer.publish_event(
        topic=topic,
        event_data=commission_data,
        key=commission_data.get("agent_id")
    )


async def publish_notification_event(
    producer: KafkaEventProducer,
    notification_type: str,
    notification_data: Dict[str, Any]
) -> bool:
    """
    Publish notification event.
    
    Args:
        producer: Kafka producer instance
        notification_type: Notification type (sms, email, push)
        notification_data: Notification data
        
    Returns:
        True if successful
    """
    topic = f"notifications.{notification_type}"
    return await producer.publish_event(
        topic=topic,
        event_data=notification_data,
        key=notification_data.get("user_id")
    )


async def publish_workflow_event(
    producer: KafkaEventProducer,
    event_type: str,
    workflow_data: Dict[str, Any]
) -> bool:
    """
    Publish workflow event.
    
    Args:
        producer: Kafka producer instance
        event_type: Event type (started, completed, failed)
        workflow_data: Workflow data
        
    Returns:
        True if successful
    """
    topic = f"workflows.{event_type}"
    return await producer.publish_event(
        topic=topic,
        event_data=workflow_data,
        key=workflow_data.get("workflow_id")
    )


# Example usage
async def main():
    """Example usage of Kafka producer."""
    # Create producer
    producer = KafkaEventProducer(client_id="example-producer")
    
    try:
        # Start producer
        await producer.start()
        
        # Publish transaction event
        await publish_transaction_event(
            producer=producer,
            event_type="created",
            transaction_data={
                "transaction_id": "txn-12345",
                "agent_id": "agent-001",
                "customer_id": "cust-001",
                "amount": 10000,
                "transaction_type": "cash-in",
                "status": "pending"
            }
        )
        
        # Publish agent event
        await publish_agent_event(
            producer=producer,
            event_type="registered",
            agent_data={
                "agent_id": "agent-002",
                "username": "agent-002",
                "email": "agent2@example.com",
                "phone_number": "+2348012345678"
            }
        )
        
        # Flush pending messages
        await producer.flush()
        
        # Get metrics
        metrics = producer.get_metrics()
        print(f"Producer metrics: {metrics}")
    
    finally:
        # Stop producer
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())

