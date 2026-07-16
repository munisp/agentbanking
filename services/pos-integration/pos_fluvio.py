"""
Fluvio Integration for POS
Bi-directional real-time event streaming
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass, asdict
import os

logger = logging.getLogger(__name__)

# ============================================================================
# FLUVIO CONFIGURATION
# ============================================================================

FLUVIO_ENDPOINT = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")

# Fluvio topics for POS events
class FluvioTopics:
    """Fluvio topic names for POS"""
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

# ============================================================================
# EVENT MODELS
# ============================================================================

@dataclass
class POSEvent:
    """Base POS event"""
    event_id: str
    event_type: str
    timestamp: str
    merchant_id: str
    terminal_id: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class TransactionEvent(POSEvent):
    """Transaction event"""
    transaction_id: str
    amount: float
    currency: str
    payment_method: str
    status: str

@dataclass
class PaymentEvent(POSEvent):
    """Payment processing event"""
    transaction_id: str
    stage: str  # initiated, processing, approved, declined, failed
    amount: float
    currency: str

@dataclass
class DeviceEvent(POSEvent):
    """Device status event"""
    device_id: str
    device_type: str
    status: str  # online, offline, error, maintenance
    error_message: Optional[str] = None

@dataclass
class FraudAlert(POSEvent):
    """Fraud detection alert"""
    transaction_id: str
    risk_score: float
    fraud_indicators: List[str]
    action: str  # flag, block, require_approval

# ============================================================================
# FLUVIO CLIENT (Using subprocess for now, can use Python SDK when available)
# ============================================================================

class FluvioClient:
    """
    Fluvio client for POS integration
    Handles bi-directional streaming
    """
    
    def __init__(self):
        self.producers: Dict[str, Any] = {}
        self.consumers: Dict[str, Any] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.running = False
    
    async def initialize(self):
        """Initialize Fluvio connection"""
        try:
            logger.info(f"Connecting to Fluvio at {FLUVIO_ENDPOINT}")
            
            # In production, use Fluvio Python SDK
            # For now, we'll use subprocess to call fluvio CLI
            
            # Create topics if they don't exist
            await self._create_topics()
            
            # Start consumer tasks
            asyncio.create_task(self._consume_commands())
            asyncio.create_task(self._consume_config_updates())
            asyncio.create_task(self._consume_fraud_rules())
            asyncio.create_task(self._consume_price_updates())
            
            self.running = True
            logger.info("✓ Fluvio integration initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Fluvio: {e}")
            # Graceful degradation - continue without Fluvio
            self.running = False
    
    async def _create_topics(self):
        """Create Fluvio topics"""
        topics = [
            FluvioTopics.TRANSACTIONS,
            FluvioTopics.PAYMENT_EVENTS,
            FluvioTopics.DEVICE_EVENTS,
            FluvioTopics.FRAUD_ALERTS,
            FluvioTopics.ANALYTICS_EVENTS,
            FluvioTopics.COMMANDS,
            FluvioTopics.CONFIG_UPDATES,
            FluvioTopics.FRAUD_RULES,
            FluvioTopics.PRICE_UPDATES,
        ]
        
        for topic in topics:
            try:
                # Use fluvio CLI to create topic
                proc = await asyncio.create_subprocess_exec(
                    'fluvio', 'topic', 'create', topic, '--ignore-rack-assignment',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                logger.info(f"Topic created or exists: {topic}")
            except Exception as e:
                logger.warning(f"Could not create topic {topic}: {e}")
    
    # ========================================================================
    # PRODUCERS (POS → Fluvio)
    # ========================================================================
    
    async def publish_transaction(self, transaction: TransactionEvent):
        """Publish transaction event to Fluvio"""
        await self._publish(FluvioTopics.TRANSACTIONS, transaction)
    
    async def publish_payment_event(self, payment: PaymentEvent):
        """Publish payment event to Fluvio"""
        await self._publish(FluvioTopics.PAYMENT_EVENTS, payment)
    
    async def publish_device_event(self, device: DeviceEvent):
        """Publish device event to Fluvio"""
        await self._publish(FluvioTopics.DEVICE_EVENTS, device)
    
    async def publish_fraud_alert(self, alert: FraudAlert):
        """Publish fraud alert to Fluvio"""
        await self._publish(FluvioTopics.FRAUD_ALERTS, alert)
    
    async def publish_analytics_event(self, event: POSEvent):
        """Publish analytics event to Fluvio"""
        await self._publish(FluvioTopics.ANALYTICS_EVENTS, event)
    
    async def _publish(self, topic: str, event: POSEvent):
        """Generic publish to Fluvio topic"""
        try:
            # Convert event to JSON
            if hasattr(event, '__dict__'):
                event_json = json.dumps(asdict(event))
            else:
                event_json = json.dumps(event)
            
            # Use fluvio CLI to produce
            proc = await asyncio.create_subprocess_exec(
                'fluvio', 'produce', topic,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate(event_json.encode())
            
            if proc.returncode == 0:
                logger.debug(f"Published to {topic}: {event.event_type}")
            else:
                logger.error(f"Failed to publish to {topic}: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Error publishing to Fluvio: {e}")
    
    # ========================================================================
    # CONSUMERS (Fluvio → POS)
    # ========================================================================
    
    async def _consume_commands(self):
        """Consume POS commands from Fluvio"""
        await self._consume(
            FluvioTopics.COMMANDS,
            self._handle_command
        )
    
    async def _consume_config_updates(self):
        """Consume configuration updates from Fluvio"""
        await self._consume(
            FluvioTopics.CONFIG_UPDATES,
            self._handle_config_update
        )
    
    async def _consume_fraud_rules(self):
        """Consume fraud rule updates from Fluvio"""
        await self._consume(
            FluvioTopics.FRAUD_RULES,
            self._handle_fraud_rule
        )
    
    async def _consume_price_updates(self):
        """Consume price updates from Fluvio"""
        await self._consume(
            FluvioTopics.PRICE_UPDATES,
            self._handle_price_update
        )
    
    async def _consume(self, topic: str, handler: Callable):
        """Generic consumer for Fluvio topic"""
        while self.running:
            try:
                # Use fluvio CLI to consume
                proc = await asyncio.create_subprocess_exec(
                    'fluvio', 'consume', topic, '--tail',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Read events line by line
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    
                    try:
                        event_data = json.loads(line.decode())
                        await handler(event_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from {topic}: {line}")
                
            except Exception as e:
                logger.error(f"Error consuming from {topic}: {e}")
                await asyncio.sleep(5)  # Retry after delay
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    async def _handle_command(self, command: Dict[str, Any]):
        """Handle POS command"""
        logger.info(f"Received command: {command.get('command_type')}")
        
        # Dispatch to registered handlers
        command_type = command.get('command_type')
        handlers = self.event_handlers.get(f"command_{command_type}", [])
        
        for handler in handlers:
            try:
                await handler(command)
            except Exception as e:
                logger.error(f"Error handling command: {e}")
    
    async def _handle_config_update(self, config: Dict[str, Any]):
        """Handle configuration update"""
        logger.info(f"Received config update: {config.get('config_key')}")
        
        handlers = self.event_handlers.get("config_update", [])
        for handler in handlers:
            try:
                await handler(config)
            except Exception as e:
                logger.error(f"Error handling config update: {e}")
    
    async def _handle_fraud_rule(self, rule: Dict[str, Any]):
        """Handle fraud rule update"""
        logger.info(f"Received fraud rule: {rule.get('rule_id')}")
        
        handlers = self.event_handlers.get("fraud_rule", [])
        for handler in handlers:
            try:
                await handler(rule)
            except Exception as e:
                logger.error(f"Error handling fraud rule: {e}")
    
    async def _handle_price_update(self, price: Dict[str, Any]):
        """Handle price update"""
        logger.info(f"Received price update: {price.get('product_id')}")
        
        handlers = self.event_handlers.get("price_update", [])
        for handler in handlers:
            try:
                await handler(price)
            except Exception as e:
                logger.error(f"Error handling price update: {e}")
    
    # ========================================================================
    # EVENT HANDLER REGISTRATION
    # ========================================================================
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered handler for {event_type}")
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def close(self):
        """Close Fluvio connection"""
        self.running = False
        logger.info("Fluvio connection closed")

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

fluvio_client = FluvioClient()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_transaction_event(
    transaction_id: str,
    merchant_id: str,
    terminal_id: str,
    amount: float,
    currency: str,
    payment_method: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None
) -> TransactionEvent:
    """Create transaction event"""
    import uuid
    
    return TransactionEvent(
        event_id=str(uuid.uuid4()),
        event_type="transaction",
        timestamp=datetime.utcnow().isoformat(),
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        transaction_id=transaction_id,
        amount=amount,
        currency=currency,
        payment_method=payment_method,
        status=status,
        data={
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "status": status
        },
        metadata=metadata
    )

def create_payment_event(
    transaction_id: str,
    merchant_id: str,
    terminal_id: str,
    stage: str,
    amount: float,
    currency: str,
    metadata: Optional[Dict[str, Any]] = None
) -> PaymentEvent:
    """Create payment event"""
    import uuid
    
    return PaymentEvent(
        event_id=str(uuid.uuid4()),
        event_type="payment",
        timestamp=datetime.utcnow().isoformat(),
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        transaction_id=transaction_id,
        stage=stage,
        amount=amount,
        currency=currency,
        data={
            "transaction_id": transaction_id,
            "stage": stage,
            "amount": amount,
            "currency": currency
        },
        metadata=metadata
    )

def create_device_event(
    device_id: str,
    merchant_id: str,
    terminal_id: str,
    device_type: str,
    status: str,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> DeviceEvent:
    """Create device event"""
    import uuid
    
    return DeviceEvent(
        event_id=str(uuid.uuid4()),
        event_type="device",
        timestamp=datetime.utcnow().isoformat(),
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        device_id=device_id,
        device_type=device_type,
        status=status,
        error_message=error_message,
        data={
            "device_id": device_id,
            "device_type": device_type,
            "status": status,
            "error_message": error_message
        },
        metadata=metadata
    )

def create_fraud_alert(
    transaction_id: str,
    merchant_id: str,
    terminal_id: str,
    risk_score: float,
    fraud_indicators: List[str],
    action: str,
    metadata: Optional[Dict[str, Any]] = None
) -> FraudAlert:
    """Create fraud alert"""
    import uuid
    
    return FraudAlert(
        event_id=str(uuid.uuid4()),
        event_type="fraud_alert",
        timestamp=datetime.utcnow().isoformat(),
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        transaction_id=transaction_id,
        risk_score=risk_score,
        fraud_indicators=fraud_indicators,
        action=action,
        data={
            "transaction_id": transaction_id,
            "risk_score": risk_score,
            "fraud_indicators": fraud_indicators,
            "action": action
        },
        metadata=metadata
    )

