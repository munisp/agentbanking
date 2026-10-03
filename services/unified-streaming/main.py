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

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


_shutdown_handlers = _PgListStore("unified_streaming__shutdown_handlers", "UNIFIED_STREAMING_DATABASE_URL")  # round-11 wave-7 persistence

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

