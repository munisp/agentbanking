"""
Production Fluvio Client using Python SDK
Replaces subprocess CLI calls with native SDK for reliability
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

# Try to import Fluvio SDK, fall back to HTTP client if not available
try:
    from fluvio import Fluvio, FluvioConfig, Offset
    FLUVIO_SDK_AVAILABLE = True
except ImportError:
    FLUVIO_SDK_AVAILABLE = False
    logger.warning("Fluvio SDK not available, using HTTP fallback")

import httpx


# =============================================================================
# CONFIGURATION
# =============================================================================

class FluvioConfig:
    """Fluvio configuration"""
    
    def __init__(self):
        self.endpoint = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")
        self.admin_endpoint = os.getenv("FLUVIO_ADMIN_ENDPOINT", "localhost:9003")
        self.tls_enabled = os.getenv("FLUVIO_TLS_ENABLED", "false").lower() == "true"
        self.tls_ca_cert = os.getenv("FLUVIO_TLS_CA_CERT")
        self.tls_client_cert = os.getenv("FLUVIO_TLS_CLIENT_CERT")
        self.tls_client_key = os.getenv("FLUVIO_TLS_CLIENT_KEY")
        self.connection_timeout = int(os.getenv("FLUVIO_CONNECTION_TIMEOUT", "30"))
        self.request_timeout = int(os.getenv("FLUVIO_REQUEST_TIMEOUT", "60"))


# =============================================================================
# FLUVIO TOPICS
# =============================================================================

class POSFluvioTopics:
    """POS-related Fluvio topics"""
    
    # Outbound (POS → Fluvio)
    TRANSACTIONS = "pos-transactions"
    PAYMENT_EVENTS = "pos-payment-events"
    DEVICE_EVENTS = "pos-device-events"
    FRAUD_ALERTS = "pos-fraud-alerts"
    ANALYTICS_EVENTS = "pos-analytics"
    
    # Inbound (Fluvio → POS)
    COMMANDS = "pos-commands"
    CONFIG_UPDATES = "pos-config-updates"
    FRAUD_RULES = "pos-fraud-rules"
    PRICE_UPDATES = "pos-price-updates"
    
    @classmethod
    def all_topics(cls) -> List[str]:
        """Get all topic names"""
        return [
            cls.TRANSACTIONS,
            cls.PAYMENT_EVENTS,
            cls.DEVICE_EVENTS,
            cls.FRAUD_ALERTS,
            cls.ANALYTICS_EVENTS,
            cls.COMMANDS,
            cls.CONFIG_UPDATES,
            cls.FRAUD_RULES,
            cls.PRICE_UPDATES,
        ]


# =============================================================================
# NATIVE FLUVIO CLIENT (SDK-based)
# =============================================================================

class NativeFluvioClient:
    """
    Native Fluvio client using the Python SDK
    Provides reliable, high-performance streaming
    """
    
    def __init__(self, config: FluvioConfig):
        self.config = config
        self.fluvio: Optional[Fluvio] = None
        self.producers: Dict[str, Any] = {}
        self.consumers: Dict[str, Any] = {}
        self.running = False
        self.consumer_tasks: List[asyncio.Task] = []
        self.event_handlers: Dict[str, List[Callable]] = {}
    
    async def connect(self) -> bool:
        """Connect to Fluvio cluster"""
        try:
            if FLUVIO_SDK_AVAILABLE:
                self.fluvio = await Fluvio.connect()
                logger.info(f"Connected to Fluvio cluster")
                return True
            else:
                logger.warning("Fluvio SDK not available, using HTTP fallback")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to Fluvio: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Fluvio cluster"""
        self.running = False
        
        # Cancel consumer tasks
        for task in self.consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.consumer_tasks.clear()
        self.producers.clear()
        self.consumers.clear()
        
        logger.info("Disconnected from Fluvio")
    
    async def create_topics(self, topics: List[str], partitions: int = 1, replication: int = 1):
        """Create topics if they don't exist"""
        if not FLUVIO_SDK_AVAILABLE or not self.fluvio:
            logger.warning("Cannot create topics: Fluvio SDK not available")
            return
        
        try:
            admin = await self.fluvio.admin()
            
            for topic in topics:
                try:
                    await admin.create_topic(topic, partitions=partitions, replication_factor=replication)
                    logger.info(f"Created topic: {topic}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug(f"Topic already exists: {topic}")
                    else:
                        logger.warning(f"Failed to create topic {topic}: {e}")
        except Exception as e:
            logger.error(f"Failed to create topics: {e}")
    
    async def get_producer(self, topic: str):
        """Get or create a producer for a topic"""
        if topic not in self.producers:
            if FLUVIO_SDK_AVAILABLE and self.fluvio:
                self.producers[topic] = await self.fluvio.topic_producer(topic)
            else:
                self.producers[topic] = HTTPFluvioProducer(self.config, topic)
        
        return self.producers[topic]
    
    async def produce(self, topic: str, key: str, value: Dict[str, Any]) -> bool:
        """Produce a message to a topic"""
        try:
            producer = await self.get_producer(topic)
            
            message = json.dumps(value)
            
            if FLUVIO_SDK_AVAILABLE and self.fluvio:
                await producer.send(key.encode(), message.encode())
            else:
                await producer.send(key, message)
            
            logger.debug(f"Produced message to {topic}: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to produce to {topic}: {e}")
            return False
    
    async def produce_batch(self, topic: str, messages: List[tuple]) -> int:
        """Produce multiple messages to a topic"""
        success_count = 0
        
        for key, value in messages:
            if await self.produce(topic, key, value):
                success_count += 1
        
        return success_count
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type}")
    
    async def start_consumer(self, topic: str, handler: Callable, from_beginning: bool = False):
        """Start consuming from a topic"""
        self.running = True
        
        async def consume_loop():
            try:
                if FLUVIO_SDK_AVAILABLE and self.fluvio:
                    consumer = await self.fluvio.partition_consumer(topic, 0)
                    
                    offset = Offset.beginning() if from_beginning else Offset.end()
                    
                    async for record in consumer.stream(offset):
                        if not self.running:
                            break
                        
                        try:
                            value = json.loads(record.value_string())
                            await handler(value)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON from {topic}")
                        except Exception as e:
                            logger.error(f"Error handling message from {topic}: {e}")
                else:
                    # HTTP fallback consumer
                    http_consumer = HTTPFluvioConsumer(self.config, topic)
                    await http_consumer.consume(handler, self.running)
                    
            except asyncio.CancelledError:
                logger.info(f"Consumer for {topic} cancelled")
            except Exception as e:
                logger.error(f"Consumer error for {topic}: {e}")
        
        task = asyncio.create_task(consume_loop())
        self.consumer_tasks.append(task)
        logger.info(f"Started consumer for {topic}")
    
    async def start_all_consumers(self):
        """Start consumers for all inbound topics"""
        inbound_topics = [
            (POSFluvioTopics.COMMANDS, self._handle_command),
            (POSFluvioTopics.CONFIG_UPDATES, self._handle_config_update),
            (POSFluvioTopics.FRAUD_RULES, self._handle_fraud_rule),
            (POSFluvioTopics.PRICE_UPDATES, self._handle_price_update),
        ]
        
        for topic, handler in inbound_topics:
            await self.start_consumer(topic, handler)
    
    async def _handle_command(self, data: Dict[str, Any]):
        """Handle POS command"""
        command_type = data.get("command_type", "unknown")
        handlers = self.event_handlers.get(f"command_{command_type}", [])
        handlers.extend(self.event_handlers.get("command", []))
        
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Error in command handler: {e}")
    
    async def _handle_config_update(self, data: Dict[str, Any]):
        """Handle configuration update"""
        handlers = self.event_handlers.get("config_update", [])
        
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Error in config handler: {e}")
    
    async def _handle_fraud_rule(self, data: Dict[str, Any]):
        """Handle fraud rule update"""
        handlers = self.event_handlers.get("fraud_rule", [])
        
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Error in fraud rule handler: {e}")
    
    async def _handle_price_update(self, data: Dict[str, Any]):
        """Handle price update"""
        handlers = self.event_handlers.get("price_update", [])
        
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Error in price update handler: {e}")


# =============================================================================
# HTTP FALLBACK CLIENT
# =============================================================================

class HTTPFluvioProducer:
    """HTTP-based Fluvio producer fallback"""
    
    def __init__(self, config: FluvioConfig, topic: str):
        self.config = config
        self.topic = topic
        self.client = httpx.AsyncClient(timeout=config.request_timeout)
    
    async def send(self, key: str, value: str):
        """Send message via HTTP"""
        try:
            # Use Fluvio HTTP API if available
            url = f"http://{self.config.endpoint}/api/v1/topics/{self.topic}/produce"
            
            response = await self.client.post(
                url,
                json={"key": key, "value": value}
            )
            
            if response.status_code not in [200, 201, 202]:
                logger.warning(f"HTTP produce returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"HTTP produce failed: {e}")
            raise


class HTTPFluvioConsumer:
    """HTTP-based Fluvio consumer fallback"""
    
    def __init__(self, config: FluvioConfig, topic: str):
        self.config = config
        self.topic = topic
        self.client = httpx.AsyncClient(timeout=config.request_timeout)
        self.offset = 0
    
    async def consume(self, handler: Callable, running: bool):
        """Consume messages via HTTP polling"""
        while running:
            try:
                url = f"http://{self.config.endpoint}/api/v1/topics/{self.topic}/consume"
                params = {"offset": self.offset, "count": 100}
                
                response = await self.client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    messages = data.get("messages", [])
                    
                    for msg in messages:
                        try:
                            value = json.loads(msg.get("value", "{}"))
                            await handler(value)
                            self.offset = msg.get("offset", self.offset) + 1
                        except Exception as e:
                            logger.error(f"Error handling message: {e}")
                
                await asyncio.sleep(1)  # Poll interval
                
            except Exception as e:
                logger.error(f"HTTP consume error: {e}")
                await asyncio.sleep(5)


# =============================================================================
# POS FLUVIO SERVICE
# =============================================================================

class POSFluvioService:
    """
    Production POS Fluvio service
    Handles all POS event streaming with native SDK
    """
    
    def __init__(self):
        self.config = FluvioConfig()
        self.client = NativeFluvioClient(self.config)
        self.initialized = False
    
    async def initialize(self):
        """Initialize the service"""
        try:
            # Connect to Fluvio
            connected = await self.client.connect()
            
            if connected:
                # Create topics
                await self.client.create_topics(POSFluvioTopics.all_topics())
                
                # Start consumers
                await self.client.start_all_consumers()
                
                self.initialized = True
                logger.info("POS Fluvio service initialized")
            else:
                logger.warning("POS Fluvio service running in degraded mode")
                
        except Exception as e:
            logger.error(f"Failed to initialize POS Fluvio service: {e}")
    
    async def close(self):
        """Close the service"""
        await self.client.disconnect()
        self.initialized = False
        logger.info("POS Fluvio service closed")
    
    # =========================================================================
    # PRODUCERS
    # =========================================================================
    
    async def publish_transaction(
        self,
        transaction_id: str,
        merchant_id: str,
        terminal_id: str,
        amount: float,
        currency: str,
        payment_method: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish transaction event"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "transaction",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_id": transaction_id,
            "merchant_id": merchant_id,
            "terminal_id": terminal_id,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "status": status,
            "metadata": metadata or {},
        }
        
        return await self.client.produce(
            POSFluvioTopics.TRANSACTIONS,
            transaction_id,
            event
        )
    
    async def publish_payment_event(
        self,
        transaction_id: str,
        merchant_id: str,
        terminal_id: str,
        stage: str,
        amount: float,
        currency: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish payment processing event"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_id": transaction_id,
            "merchant_id": merchant_id,
            "terminal_id": terminal_id,
            "stage": stage,
            "amount": amount,
            "currency": currency,
            "metadata": metadata or {},
        }
        
        return await self.client.produce(
            POSFluvioTopics.PAYMENT_EVENTS,
            transaction_id,
            event
        )
    
    async def publish_device_event(
        self,
        device_id: str,
        merchant_id: str,
        terminal_id: str,
        device_type: str,
        status: str,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish device status event"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "device",
            "timestamp": datetime.utcnow().isoformat(),
            "device_id": device_id,
            "merchant_id": merchant_id,
            "terminal_id": terminal_id,
            "device_type": device_type,
            "status": status,
            "error_message": error_message,
            "metadata": metadata or {},
        }
        
        return await self.client.produce(
            POSFluvioTopics.DEVICE_EVENTS,
            device_id,
            event
        )
    
    async def publish_fraud_alert(
        self,
        transaction_id: str,
        merchant_id: str,
        terminal_id: str,
        risk_score: float,
        fraud_indicators: List[str],
        action: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish fraud detection alert"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "fraud_alert",
            "timestamp": datetime.utcnow().isoformat(),
            "transaction_id": transaction_id,
            "merchant_id": merchant_id,
            "terminal_id": terminal_id,
            "risk_score": risk_score,
            "fraud_indicators": fraud_indicators,
            "action": action,
            "metadata": metadata or {},
        }
        
        return await self.client.produce(
            POSFluvioTopics.FRAUD_ALERTS,
            transaction_id,
            event
        )
    
    async def publish_analytics_event(
        self,
        event_type: str,
        merchant_id: str,
        terminal_id: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish analytics event"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "merchant_id": merchant_id,
            "terminal_id": terminal_id,
            "data": data,
            "metadata": metadata or {},
        }
        
        return await self.client.produce(
            POSFluvioTopics.ANALYTICS_EVENTS,
            f"{merchant_id}_{terminal_id}",
            event
        )
    
    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    
    def register_command_handler(self, handler: Callable):
        """Register handler for POS commands"""
        self.client.register_handler("command", handler)
    
    def register_config_handler(self, handler: Callable):
        """Register handler for config updates"""
        self.client.register_handler("config_update", handler)
    
    def register_fraud_rule_handler(self, handler: Callable):
        """Register handler for fraud rule updates"""
        self.client.register_handler("fraud_rule", handler)
    
    def register_price_handler(self, handler: Callable):
        """Register handler for price updates"""
        self.client.register_handler("price_update", handler)


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

pos_fluvio_service = POSFluvioService()


async def initialize_fluvio():
    """Initialize the global Fluvio service"""
    await pos_fluvio_service.initialize()


async def close_fluvio():
    """Close the global Fluvio service"""
    await pos_fluvio_service.close()
