"""
Kafka Consumer Module
Implements Kafka consumer for inventory events processing
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from service_config import get_config

logger = logging.getLogger(__name__)


class InventoryEventType(str, Enum):
    """Inventory event types"""
    STOCK_UPDATED = "stock.updated"
    STOCK_RESERVED = "stock.reserved"
    STOCK_RELEASED = "stock.released"
    STOCK_FULFILLED = "stock.fulfilled"
    LOW_STOCK_ALERT = "stock.low_alert"
    OUT_OF_STOCK = "stock.out_of_stock"
    RESTOCK_RECEIVED = "stock.restock_received"
    INVENTORY_ADJUSTMENT = "stock.adjustment"
    WAREHOUSE_TRANSFER = "stock.transfer"


@dataclass
class InventoryEvent:
    """Inventory event"""
    event_id: str
    event_type: InventoryEventType
    timestamp: datetime
    warehouse_id: str
    product_id: str
    sku: str
    quantity_change: int
    quantity_available: int
    quantity_reserved: int
    metadata: Dict[str, Any]


class InventoryEventConsumer:
    """
    Kafka consumer for inventory events
    
    Features:
    - Consumes inventory events from Kafka
    - Processes stock updates, reservations, alerts
    - Dead letter queue for failed messages
    - Batch processing for efficiency
    - Graceful shutdown
    """
    
    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        consumer_group: Optional[str] = None,
        topics: Optional[List[str]] = None
    ):
        config = get_config()
        self.bootstrap_servers = bootstrap_servers or config.kafka.bootstrap_servers
        self.consumer_group = consumer_group or config.kafka.consumer_group
        self.topics = topics or [
            config.kafka.inventory_events_topic,
            "inventory.sync",
            "inventory.alerts"
        ]
        
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._producer: Optional[AIOKafkaProducer] = None
        self._handlers: Dict[InventoryEventType, List[Callable]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the consumer"""
        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode("utf-8"))
        )
        
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8")
        )
        
        await self._consumer.start()
        await self._producer.start()
        
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        
        logger.info(f"Inventory event consumer started, topics: {self.topics}")
    
    async def stop(self):
        """Stop the consumer"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._consumer:
            await self._consumer.stop()
        
        if self._producer:
            await self._producer.stop()
        
        logger.info("Inventory event consumer stopped")
    
    def register_handler(
        self,
        event_type: InventoryEventType,
        handler: Callable[[InventoryEvent], Any]
    ):
        """Register a handler for an event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def _consume_loop(self):
        """Main consume loop"""
        while self._running:
            try:
                async for message in self._consumer:
                    try:
                        await self._process_message(message)
                        await self._consumer.commit()
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await self._send_to_dlq(message, str(e))
                        await self._consumer.commit()
            except asyncio.CancelledError:
                break
            except KafkaError as e:
                logger.error(f"Kafka error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in consume loop: {e}")
                await asyncio.sleep(5)
    
    async def _process_message(self, message):
        """Process a single message"""
        data = message.value
        
        try:
            event = InventoryEvent(
                event_id=data.get("event_id", ""),
                event_type=InventoryEventType(data.get("event_type", "")),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
                warehouse_id=data.get("warehouse_id", ""),
                product_id=data.get("product_id", ""),
                sku=data.get("sku", ""),
                quantity_change=data.get("quantity_change", 0),
                quantity_available=data.get("quantity_available", 0),
                quantity_reserved=data.get("quantity_reserved", 0),
                metadata=data.get("metadata", {})
            )
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid event format: {e}")
            raise
        
        handlers = self._handlers.get(event.event_type, [])
        
        if not handlers:
            logger.debug(f"No handlers for event type {event.event_type}")
            return
        
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Handler error for {event.event_type}: {e}")
                raise
        
        logger.debug(f"Processed event {event.event_id} ({event.event_type})")
    
    async def _send_to_dlq(self, message, error: str):
        """Send failed message to dead letter queue"""
        dlq_message = {
            "original_topic": message.topic,
            "original_partition": message.partition,
            "original_offset": message.offset,
            "original_value": message.value,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            await self._producer.send_and_wait(
                "inventory.events.dlq",
                dlq_message
            )
            logger.warning(f"Sent message to DLQ: {error}")
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")


class InventoryEventProducer:
    """
    Kafka producer for inventory events
    
    Features:
    - Publishes inventory events to Kafka
    - Batch publishing for efficiency
    - Retry logic for failed sends
    """
    
    def __init__(self, bootstrap_servers: Optional[str] = None):
        config = get_config()
        self.bootstrap_servers = bootstrap_servers or config.kafka.bootstrap_servers
        self.topic = config.kafka.inventory_events_topic
        self._producer: Optional[AIOKafkaProducer] = None
    
    async def start(self):
        """Start the producer"""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            acks="all",
            retries=3
        )
        await self._producer.start()
        logger.info("Inventory event producer started")
    
    async def stop(self):
        """Stop the producer"""
        if self._producer:
            await self._producer.stop()
        logger.info("Inventory event producer stopped")
    
    async def publish(self, event: InventoryEvent):
        """Publish a single event"""
        if not self._producer:
            raise RuntimeError("Producer not started")
        
        message = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "warehouse_id": event.warehouse_id,
            "product_id": event.product_id,
            "sku": event.sku,
            "quantity_change": event.quantity_change,
            "quantity_available": event.quantity_available,
            "quantity_reserved": event.quantity_reserved,
            "metadata": event.metadata
        }
        
        await self._producer.send_and_wait(self.topic, message)
        logger.debug(f"Published event {event.event_id}")
    
    async def publish_batch(self, events: List[InventoryEvent]):
        """Publish multiple events"""
        if not self._producer:
            raise RuntimeError("Producer not started")
        
        batch = self._producer.create_batch()
        
        for event in events:
            message = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "warehouse_id": event.warehouse_id,
                "product_id": event.product_id,
                "sku": event.sku,
                "quantity_change": event.quantity_change,
                "quantity_available": event.quantity_available,
                "quantity_reserved": event.quantity_reserved,
                "metadata": event.metadata
            }
            
            serialized = json.dumps(message, default=str).encode("utf-8")
            batch.append(value=serialized, timestamp=None, key=None)
        
        await self._producer.send_batch(batch, self.topic, partition=0)
        logger.info(f"Published batch of {len(events)} events")
    
    async def publish_stock_update(
        self,
        warehouse_id: str,
        product_id: str,
        sku: str,
        quantity_change: int,
        quantity_available: int,
        quantity_reserved: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Convenience method to publish stock update event"""
        import uuid
        
        event = InventoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=InventoryEventType.STOCK_UPDATED,
            timestamp=datetime.utcnow(),
            warehouse_id=warehouse_id,
            product_id=product_id,
            sku=sku,
            quantity_change=quantity_change,
            quantity_available=quantity_available,
            quantity_reserved=quantity_reserved,
            metadata=metadata or {}
        )
        
        await self.publish(event)
    
    async def publish_low_stock_alert(
        self,
        warehouse_id: str,
        product_id: str,
        sku: str,
        quantity_available: int,
        reorder_point: int
    ):
        """Convenience method to publish low stock alert"""
        import uuid
        
        event = InventoryEvent(
            event_id=str(uuid.uuid4()),
            event_type=InventoryEventType.LOW_STOCK_ALERT,
            timestamp=datetime.utcnow(),
            warehouse_id=warehouse_id,
            product_id=product_id,
            sku=sku,
            quantity_change=0,
            quantity_available=quantity_available,
            quantity_reserved=0,
            metadata={
                "reorder_point": reorder_point,
                "deficit": reorder_point - quantity_available
            }
        )
        
        await self.publish(event)


# Default handlers for common inventory events
async def handle_low_stock_alert(event: InventoryEvent):
    """Handle low stock alert - trigger reorder workflow"""
    logger.warning(
        f"Low stock alert: {event.sku} at warehouse {event.warehouse_id}, "
        f"available: {event.quantity_available}"
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.post(
                f"{os.getenv('TEMPORAL_URL', 'http://temporal:7233')}/api/v1/workflows/reorder",
                json={
                    "sku": event.sku,
                    "warehouse_id": event.warehouse_id,
                    "current_quantity": event.quantity_available,
                    "reorder_quantity": event.quantity_available * 3,
                },
            )
        except Exception as exc:
            logger.error(f"Failed to trigger reorder workflow: {exc}")


async def handle_out_of_stock(event: InventoryEvent):
    """Handle out of stock - update product availability"""
    logger.error(
        f"Out of stock: {event.sku} at warehouse {event.warehouse_id}"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.patch(
                f"{os.getenv('DATABASE_SERVICE_URL', 'http://database-service:8080')}/api/v1/products/{event.sku}/availability",
                json={"available": False, "warehouse_id": event.warehouse_id},
            )
        except Exception as exc:
            logger.error(f"Failed to update product availability: {exc}")


async def handle_stock_reserved(event: InventoryEvent):
    """Handle stock reserved - log for analytics"""
    logger.info(
        f"Stock reserved: {event.quantity_change} units of {event.sku} "
        f"at warehouse {event.warehouse_id}"
    )


def create_default_consumer() -> InventoryEventConsumer:
    """Create consumer with default handlers"""
    consumer = InventoryEventConsumer()
    
    consumer.register_handler(InventoryEventType.LOW_STOCK_ALERT, handle_low_stock_alert)
    consumer.register_handler(InventoryEventType.OUT_OF_STOCK, handle_out_of_stock)
    consumer.register_handler(InventoryEventType.STOCK_RESERVED, handle_stock_reserved)
    
    return consumer
