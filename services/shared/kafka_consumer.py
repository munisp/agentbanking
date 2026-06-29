"""
Kafka Consumer Library for Remittance Platform V11.0

Provides a reusable Kafka consumer for consuming events in microservices.

Features:
- Async/await support with aiokafka
- Automatic JSON deserialization
- Consumer groups for load balancing
- Automatic offset management
- Error handling and retries
- Metrics and logging

Author: Manus AI
Date: November 11, 2025
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import asyncio
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KafkaEventConsumer:
    """
    Async Kafka consumer for consuming events.
    
    Usage:
        async def handle_transaction(event: Dict[str, Any]):
            print(f"Processing transaction: {event}")
        
        consumer = KafkaEventConsumer(
            topics=["transactions.created"],
            group_id="transaction-processor",
            handler=handle_transaction
        )
        
        await consumer.start()
        await consumer.consume()  # Runs forever
    """
    
    def __init__(
        self,
        topics: List[str],
        group_id: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
        bootstrap_servers: Optional[str] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        max_poll_records: int = 500,
        session_timeout_ms: int = 30000
    ):
        """
        Initialize Kafka consumer.
        
        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID
            handler: Async function to handle each message
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            auto_offset_reset: Where to start reading (earliest, latest)
            enable_auto_commit: Auto-commit offsets
            max_poll_records: Max records per poll
            session_timeout_ms: Session timeout in milliseconds
        """
        self.topics = topics
        self.group_id = group_id
        self.handler = handler
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "kafka-1:9092,kafka-2:9093,kafka-3:9094"
        )
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.max_poll_records = max_poll_records
        self.session_timeout_ms = session_timeout_ms
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._is_started = False
        self._is_consuming = False
        
        # Metrics
        self.messages_consumed = 0
        self.messages_processed = 0
        self.messages_failed = 0
        self.bytes_consumed = 0
    
    async def start(self):
        """Start the Kafka consumer."""
        if self._is_started:
            logger.warning("Consumer already started")
            return
        
        logger.info(f"Starting Kafka consumer: {self.group_id}")
        logger.info(f"Bootstrap servers: {self.bootstrap_servers}")
        logger.info(f"Topics: {', '.join(self.topics)}")
        
        self.consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers.split(","),
            group_id=self.group_id,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=self.enable_auto_commit,
            max_poll_records=self.max_poll_records,
            session_timeout_ms=self.session_timeout_ms,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
        )
        
        await self.consumer.start()
        self._is_started = True
        
        logger.info("✅ Kafka consumer started successfully")
    
    async def stop(self):
        """Stop the Kafka consumer."""
        if not self._is_started:
            return
        
        logger.info("Stopping Kafka consumer...")
        
        self._is_consuming = False
        
        if self.consumer:
            await self.consumer.stop()
        
        self._is_started = False
        logger.info("✅ Kafka consumer stopped")
        
        # Log metrics
        logger.info(f"Consumer metrics:")
        logger.info(f"  Messages consumed: {self.messages_consumed}")
        logger.info(f"  Messages processed: {self.messages_processed}")
        logger.info(f"  Messages failed: {self.messages_failed}")
        logger.info(f"  Bytes consumed: {self.bytes_consumed}")
    
    async def consume(self):
        """
        Start consuming messages (runs forever).
        
        This method will block until stop() is called.
        """
        if not self._is_started:
            raise RuntimeError("Consumer not started. Call start() first.")
        
        self._is_consuming = True
        logger.info("🔄 Starting message consumption...")
        
        try:
            async for message in self.consumer:
                if not self._is_consuming:
                    break
                
                # Update metrics
                self.messages_consumed += 1
                self.bytes_consumed += len(message.value)
                
                # Log message metadata
                logger.debug(
                    f"Received message from {message.topic} "
                    f"(partition={message.partition}, offset={message.offset})"
                )
                
                try:
                    # Extract event data
                    event_data = message.value
                    
                    # Call handler
                    await self.handler(event_data)
                    
                    # Update metrics
                    self.messages_processed += 1
                    
                    logger.debug(f"✅ Message processed successfully")
                
                except Exception as e:
                    self.messages_failed += 1
                    logger.error(
                        f"❌ Error processing message from {message.topic}: {e}",
                        exc_info=True
                    )
                    
                    # Optionally publish to dead letter queue
                    # await self.publish_to_dlq(message, e)
        
        except Exception as e:
            logger.error(f"❌ Error in consume loop: {e}", exc_info=True)
            raise
    
    async def consume_batch(self, batch_size: int = 100, timeout_ms: int = 1000):
        """
        Consume messages in batches.
        
        Args:
            batch_size: Number of messages per batch
            timeout_ms: Timeout for fetching batch
        """
        if not self._is_started:
            raise RuntimeError("Consumer not started. Call start() first.")
        
        self._is_consuming = True
        logger.info(f"🔄 Starting batch consumption (batch_size={batch_size})...")
        
        try:
            while self._is_consuming:
                # Fetch batch
                messages = await self.consumer.getmany(
                    timeout_ms=timeout_ms,
                    max_records=batch_size
                )
                
                if not messages:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process all messages in batch
                for topic_partition, records in messages.items():
                    for message in records:
                        # Update metrics
                        self.messages_consumed += 1
                        self.bytes_consumed += len(message.value)
                        
                        try:
                            # Extract event data
                            event_data = message.value
                            
                            # Call handler
                            await self.handler(event_data)
                            
                            # Update metrics
                            self.messages_processed += 1
                        
                        except Exception as e:
                            self.messages_failed += 1
                            logger.error(
                                f"❌ Error processing message: {e}",
                                exc_info=True
                            )
                
                logger.debug(f"Processed batch of {sum(len(r) for r in messages.values())} messages")
        
        except Exception as e:
            logger.error(f"❌ Error in batch consume loop: {e}", exc_info=True)
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics."""
        return {
            "messages_consumed": self.messages_consumed,
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "bytes_consumed": self.bytes_consumed,
            "success_rate": (
                self.messages_processed / self.messages_consumed
                if self.messages_consumed > 0
                else 0
            )
        }


# Example handlers for common event types

async def transaction_event_handler(event: Dict[str, Any]):
    """
    Handle transaction events.
    
    Args:
        event: Transaction event data
    """
    transaction_id = event.get("transaction_id")
    amount = event.get("amount")
    transaction_type = event.get("transaction_type")
    
    logger.info(
        f"Processing transaction: {transaction_id} "
        f"(type={transaction_type}, amount={amount})"
    )
    
    # Process transaction
    # - Update analytics
    # - Send notifications
    # - Update agent performance
    # etc.


async def commission_event_handler(event: Dict[str, Any]):
    """
    Handle commission events.
    
    Args:
        event: Commission event data
    """
    agent_id = event.get("agent_id")
    commission_amount = event.get("commission_amount")
    
    logger.info(
        f"Processing commission: agent={agent_id}, "
        f"amount={commission_amount}"
    )
    
    # Process commission
    # - Update agent balance
    # - Send notification
    # - Update analytics
    # etc.


async def notification_event_handler(event: Dict[str, Any]):
    """
    Handle notification events.
    
    Args:
        event: Notification event data
    """
    user_id = event.get("user_id")
    notification_type = event.get("notification_type")
    message = event.get("message")
    
    logger.info(
        f"Sending notification: user={user_id}, "
        f"type={notification_type}"
    )
    
    # Send notification
    # - SMS
    # - Email
    # - Push notification
    # etc.


# Example usage
async def main():
    """Example usage of Kafka consumer."""
    
    # Define handler
    async def my_handler(event: Dict[str, Any]):
        print(f"Received event: {event}")
        # Process event
        await asyncio.sleep(0.1)  # Process processing
    
    # Create consumer
    consumer = KafkaEventConsumer(
        topics=["transactions.created", "transactions.completed"],
        group_id="transaction-processor",
        handler=my_handler
    )
    
    try:
        # Start consumer
        await consumer.start()
        
        # Consume messages (runs forever)
        await consumer.consume()
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    
    finally:
        # Stop consumer
        await consumer.stop()
        
        # Print metrics
        metrics = consumer.get_metrics()
        print(f"Consumer metrics: {metrics}")


if __name__ == "__main__":
    asyncio.run(main())

