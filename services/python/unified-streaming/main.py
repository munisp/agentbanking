#!/usr/bin/env python3
"""
Unified Streaming Platform - Fluvio + Kafka Integration
Seamless integration between Fluvio and Kafka for Remittance Platform
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable, Literal
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


# Fluvio client
try:
    from fluvio import Fluvio, Offset
    FLUVIO_AVAILABLE = True
except ImportError:
    FLUVIO_AVAILABLE = False
    logging.warning("⚠️ Fluvio not installed")

# Kafka client
try:
    from kafka import KafkaProducer, KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logging.warning("⚠️ Kafka not installed")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Enums and Data Models
# ============================================================================

class StreamingPlatform(str, Enum):
    """Streaming platform types"""
    FLUVIO = "fluvio"
    KAFKA = "kafka"
    BOTH = "both"


class RoutingStrategy(str, Enum):
    """Event routing strategies"""
    FLUVIO_ONLY = "fluvio_only"
    KAFKA_ONLY = "kafka_only"
    FLUVIO_PRIMARY = "fluvio_primary"  # Fluvio primary, Kafka backup
    KAFKA_PRIMARY = "kafka_primary"  # Kafka primary, Fluvio backup
    DUAL_WRITE = "dual_write"  # Write to both
    SMART_ROUTE = "smart_route"  # Route based on event type


@dataclass
class BankingEvent:
    """Banking event structure"""
    event_id: str
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    data: Dict[str, Any]
    timestamp: str
    source_service: str
    correlation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    platform: Optional[str] = None  # Which platform produced this


class ProduceRequest(BaseModel):
    """Request model for producing events"""
    topic: str = Field(..., description="Topic name")
    event_type: str = Field(..., description="Type of event")
    entity_type: str = Field(..., description="Type of entity")
    entity_id: str = Field(..., description="Entity ID")
    action: str = Field(..., description="Action performed")
    data: Dict[str, Any] = Field(..., description="Event data")
    source_service: str = Field(..., description="Source service")
    platform: Optional[StreamingPlatform] = Field(None, description="Target platform")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")


# ============================================================================
# Topic Configuration
# ============================================================================

TOPIC_CONFIG = {
    # Real-time, low-latency events → Fluvio
    "banking.transactions": {"platform": StreamingPlatform.FLUVIO, "priority": "high"},
    "banking.fraud.alerts": {"platform": StreamingPlatform.FLUVIO, "priority": "high"},
    "banking.payments.qr": {"platform": StreamingPlatform.FLUVIO, "priority": "high"},
    "banking.payments.ussd": {"platform": StreamingPlatform.FLUVIO, "priority": "high"},
    
    # High-throughput, batch events → Kafka
    "banking.analytics.events": {"platform": StreamingPlatform.KAFKA, "priority": "normal"},
    "banking.audit.logs": {"platform": StreamingPlatform.KAFKA, "priority": "normal"},
    "banking.compliance.events": {"platform": StreamingPlatform.KAFKA, "priority": "normal"},
    
    # Critical events → Both (dual write)
    "banking.kyb.decisions": {"platform": StreamingPlatform.BOTH, "priority": "critical"},
    "banking.insurance.claims": {"platform": StreamingPlatform.BOTH, "priority": "critical"},
    
    # Default → Smart routing
    "banking.kyb.applications": {"platform": "smart", "priority": "normal"},
    "banking.kyb.documents": {"platform": "smart", "priority": "normal"},
    "banking.payments.sms": {"platform": "smart", "priority": "normal"},
    "banking.payments.whatsapp": {"platform": "smart", "priority": "normal"},
    "banking.insurance.policies": {"platform": "smart", "priority": "normal"},
    "banking.agents.performance": {"platform": "smart", "priority": "normal"},
    "banking.agents.onboarding": {"platform": "smart", "priority": "normal"},
    "banking.customers.activity": {"platform": "smart", "priority": "normal"},
    "banking.notifications": {"platform": "smart", "priority": "normal"},
}


# ============================================================================
# Unified Streaming Platform
# ============================================================================

class UnifiedStreamingPlatform:
    """Unified streaming platform integrating Fluvio and Kafka"""
    
    def __init__(self, routing_strategy: RoutingStrategy = RoutingStrategy.SMART_ROUTE):
        self.routing_strategy = routing_strategy
        
        # Fluvio components
        self.fluvio_client: Optional[Fluvio] = None
        self.fluvio_producers: Dict[str, Any] = {}
        self.fluvio_consumers: Dict[str, Any] = {}
        
        # Kafka components
        self.kafka_producer: Optional[KafkaProducer] = None
        self.kafka_consumers: Dict[str, KafkaConsumer] = {}
        
        # Metrics
        self.metrics = {
            "fluvio": {"produced": 0, "consumed": 0, "errors": 0},
            "kafka": {"produced": 0, "consumed": 0, "errors": 0},
            "bridge": {"fluvio_to_kafka": 0, "kafka_to_fluvio": 0},
            "total": {"produced": 0, "consumed": 0, "errors": 0}
        }
        
        # Event bridge queue
        self.bridge_queue: asyncio.Queue = asyncio.Queue()
        
    async def initialize(self) -> bool:
        """Initialize both Fluvio and Kafka"""
        success = True
        
        # Initialize Fluvio
        if FLUVIO_AVAILABLE:
            try:
                self.fluvio_client = await Fluvio.connect()
                admin = await self.fluvio_client.admin()
                
                # Create Fluvio topics
                fluvio_topics = [t for t, c in TOPIC_CONFIG.items() 
                               if c["platform"] in [StreamingPlatform.FLUVIO, StreamingPlatform.BOTH, "smart"]]
                
                for topic in fluvio_topics:
                    try:
                        topics_list = await admin.list_topics()
                        if not any(t.name == topic for t in topics_list):
                            await admin.create_topic(topic, replication=3, partitions=6)
                            logger.info(f"✅ Created Fluvio topic: {topic}")
                    except Exception as e:
                        logger.warning(f"⚠️ Fluvio topic {topic}: {str(e)}")
                
                logger.info("✅ Fluvio initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Fluvio: {str(e)}")
                success = False
        else:
            logger.warning("⚠️ Fluvio not available")
        
        # Initialize Kafka
        if KAFKA_AVAILABLE:
            try:
                bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
                
                self.kafka_producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None,
                    acks='all',
                    retries=3,
                    compression_type='snappy',
                    batch_size=16384,
                    linger_ms=10,
                    enable_idempotence=True
                )
                
                logger.info("✅ Kafka initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Kafka: {str(e)}")
                success = False
        else:
            logger.warning("⚠️ Kafka not available")
        
        # Start event bridge
        if FLUVIO_AVAILABLE and KAFKA_AVAILABLE:
            asyncio.create_task(self._run_event_bridge())
            logger.info("✅ Event bridge started")
        
        return success
    
    def _determine_platform(self, topic: str, event_type: str) -> StreamingPlatform:
        """Determine which platform to use for an event"""
        # Check topic configuration
        if topic in TOPIC_CONFIG:
            platform = TOPIC_CONFIG[topic]["platform"]
            
            if platform == StreamingPlatform.FLUVIO:
                return StreamingPlatform.FLUVIO
            elif platform == StreamingPlatform.KAFKA:
                return StreamingPlatform.KAFKA
            elif platform == StreamingPlatform.BOTH:
                return StreamingPlatform.BOTH
        
        # Smart routing based on event type
        if self.routing_strategy == RoutingStrategy.SMART_ROUTE:
            # Real-time events → Fluvio
            if event_type in ["transaction", "payment", "fraud_alert"]:
                return StreamingPlatform.FLUVIO
            # Batch/analytics events → Kafka
            elif event_type in ["analytics", "audit", "compliance"]:
                return StreamingPlatform.KAFKA
        
        # Fallback based on routing strategy
        if self.routing_strategy == RoutingStrategy.FLUVIO_PRIMARY:
            return StreamingPlatform.FLUVIO if FLUVIO_AVAILABLE else StreamingPlatform.KAFKA
        elif self.routing_strategy == RoutingStrategy.KAFKA_PRIMARY:
            return StreamingPlatform.KAFKA if KAFKA_AVAILABLE else StreamingPlatform.FLUVIO
        elif self.routing_strategy == RoutingStrategy.DUAL_WRITE:
            return StreamingPlatform.BOTH
        
        # Default to Fluvio
        return StreamingPlatform.FLUVIO if FLUVIO_AVAILABLE else StreamingPlatform.KAFKA
    
    async def produce_event(
        self,
        topic: str,
        event: BankingEvent,
        platform: Optional[StreamingPlatform] = None
    ) -> Dict[str, bool]:
        """Produce event to Fluvio, Kafka, or both"""
        # Determine target platform
        if platform is None:
            platform = self._determine_platform(topic, event.event_type)
        
        results = {"fluvio": False, "kafka": False}
        
        # Produce to Fluvio
        if platform in [StreamingPlatform.FLUVIO, StreamingPlatform.BOTH]:
            if FLUVIO_AVAILABLE and self.fluvio_client:
                try:
                    # Get or create producer
                    if topic not in self.fluvio_producers:
                        self.fluvio_producers[topic] = await self.fluvio_client.topic_producer(topic)
                    
                    producer = self.fluvio_producers[topic]
                    
                    # Set platform metadata
                    event.platform = "fluvio"
                    event_data = json.dumps(asdict(event))
                    
                    # Produce with key
                    await producer.send(event.entity_id, event_data)
                    await producer.flush()
                    
                    self.metrics["fluvio"]["produced"] += 1
                    self.metrics["total"]["produced"] += 1
                    results["fluvio"] = True
                    
                    logger.info(f"📤 Fluvio: {topic} → {event.event_type}")
                    
                except Exception as e:
                    self.metrics["fluvio"]["errors"] += 1
                    self.metrics["total"]["errors"] += 1
                    logger.error(f"❌ Fluvio produce error: {str(e)}")
        
        # Produce to Kafka
        if platform in [StreamingPlatform.KAFKA, StreamingPlatform.BOTH]:
            if KAFKA_AVAILABLE and self.kafka_producer:
                try:
                    # Set platform metadata
                    event.platform = "kafka"
                    event_data = asdict(event)
                    
                    # Produce with key
                    future = self.kafka_producer.send(
                        topic,
                        value=event_data,
                        key=event.entity_id
                    )
                    
                    # Wait for send
                    record_metadata = future.get(timeout=10)
                    
                    self.metrics["kafka"]["produced"] += 1
                    self.metrics["total"]["produced"] += 1
                    results["kafka"] = True
                    
                    logger.info(f"📤 Kafka: {topic} → {event.event_type} (partition {record_metadata.partition})")
                    
                except Exception as e:
                    self.metrics["kafka"]["errors"] += 1
                    self.metrics["total"]["errors"] += 1
                    logger.error(f"❌ Kafka produce error: {str(e)}")
        
        return results
    
    async def _run_event_bridge(self):
        """Run event bridge to sync between Fluvio and Kafka"""
        logger.info("🌉 Event bridge running...")
        
        while True:
            try:
                # Get event from bridge queue
                bridge_event = await asyncio.wait_for(
                    self.bridge_queue.get(),
                    timeout=1.0
                )
                
                source_platform = bridge_event["source"]
                target_platform = bridge_event["target"]
                topic = bridge_event["topic"]
                event = bridge_event["event"]
                
                # Bridge event
                if target_platform == "kafka":
                    await self.produce_event(topic, event, StreamingPlatform.KAFKA)
                    self.metrics["bridge"]["fluvio_to_kafka"] += 1
                elif target_platform == "fluvio":
                    await self.produce_event(topic, event, StreamingPlatform.FLUVIO)
                    self.metrics["bridge"]["kafka_to_fluvio"] += 1
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Event bridge error: {str(e)}")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get unified metrics"""
        return {
            "platforms": {
                "fluvio": {
                    "available": FLUVIO_AVAILABLE,
                    "connected": self.fluvio_client is not None,
                    **self.metrics["fluvio"]
                },
                "kafka": {
                    "available": KAFKA_AVAILABLE,
                    "connected": self.kafka_producer is not None,
                    **self.metrics["kafka"]
                }
            },
            "bridge": self.metrics["bridge"],
            "total": self.metrics["total"],
            "routing_strategy": self.routing_strategy.value
        }
    
    async def close(self):
        """Close all connections"""
        # Close Fluvio
        if self.fluvio_client:
            for producer in self.fluvio_producers.values():
                try:
                    await producer.flush()
                except Exception as e:
                    logger.error(f"⚠️ Error flushing Fluvio producer: {str(e)}")
            self.fluvio_producers.clear()
        
        # Close Kafka
        if self.kafka_producer:
            try:
                self.kafka_producer.flush()
                self.kafka_producer.close()
            except Exception as e:
                logger.error(f"⚠️ Error closing Kafka producer: {str(e)}")
        
        logger.info("✅ Unified streaming platform closed")


# ============================================================================
# FastAPI Application
# ============================================================================

streaming_platform: Optional[UnifiedStreamingPlatform] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager"""
    global streaming_platform
    
    # Startup
    logger.info("🚀 Starting unified streaming platform...")
    
    routing_strategy = RoutingStrategy(os.getenv("ROUTING_STRATEGY", "smart_route"))
    streaming_platform = UnifiedStreamingPlatform(routing_strategy)
    await streaming_platform.initialize()
    
    yield
    
    # Shutdown
    logger.info("⏹️ Shutting down unified streaming platform...")
    if streaming_platform:
        await streaming_platform.close()


app = FastAPI(
    title="Unified Streaming Platform",
    description="Fluvio + Kafka Integration for Remittance Platform",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "unified-streaming",
        "version": "1.0.0",
        "platforms": {
            "fluvio": FLUVIO_AVAILABLE,
            "kafka": KAFKA_AVAILABLE
        }
    }


@app.get("/health")
async def health_check():
    """Health check"""
    if not streaming_platform:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "status": "healthy",
        "fluvio": {
            "available": FLUVIO_AVAILABLE,
            "connected": streaming_platform.fluvio_client is not None
        },
        "kafka": {
            "available": KAFKA_AVAILABLE,
            "connected": streaming_platform.kafka_producer is not None
        }
    }


@app.get("/metrics")
async def get_metrics():
    """Get metrics"""
    if not streaming_platform:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return await streaming_platform.get_metrics()


@app.get("/topics")
async def list_topics():
    """List topics and their routing"""
    return {
        "topics": TOPIC_CONFIG,
        "count": len(TOPIC_CONFIG)
    }


@app.post("/produce")
async def produce_event(request: ProduceRequest):
    """Produce event to unified platform"""
    if not streaming_platform:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Create event
    event = BankingEvent(
        event_id=str(uuid.uuid4()),
        event_type=request.event_type,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        action=request.action,
        data=request.data,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_service=request.source_service,
        correlation_id=request.correlation_id,
        tenant_id=request.tenant_id
    )
    
    # Produce
    results = await streaming_platform.produce_event(
        request.topic,
        event,
        request.platform
    )
    
    if not any(results.values()):
        raise HTTPException(status_code=500, detail="Failed to produce to any platform")
    
    return {
        "status": "success",
        "event_id": event.event_id,
        "topic": request.topic,
        "platforms": results
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8097"))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )

