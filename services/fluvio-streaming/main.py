#!/usr/bin/env python3
"""
Production-Ready Fluvio Streaming Service for Remittance Platform
Real Fluvio client integration with Python
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable
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


_shutdown_handlers = []  # function registry — must stay in-process (wave-8 revert of wave-7 overreach)  # round-11 wave-7 persistence

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


# Real Fluvio Python client
try:
    from fluvio import Fluvio, Offset
    FLUVIO_AVAILABLE = True
except ImportError:
    FLUVIO_AVAILABLE = False
    logging.warning("⚠️ Fluvio not installed. Install with: pip install fluvio")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class BankingEvent:
    """Banking-specific event structure"""
    event_id: str
    event_type: str  # transaction, kyb, payment, insurance, etc.
    entity_type: str  # customer, agent, account, etc.
    entity_id: str
    action: str  # create, update, delete, approve, etc.
    data: Dict[str, Any]
    timestamp: str
    source_service: str
    correlation_id: Optional[str] = None
    tenant_id: Optional[str] = None


class ProduceRequest(BaseModel):
    """Request model for producing events"""
    event_type: str = Field(..., description="Type of event")
    entity_type: str = Field(..., description="Type of entity")
    entity_id: str = Field(..., description="Entity ID")
    action: str = Field(..., description="Action performed")
    data: Dict[str, Any] = Field(..., description="Event data")
    source_service: str = Field(..., description="Source service")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")


# ============================================================================
# Fluvio Streaming Service
# ============================================================================

class FluvioStreamingService:
    """Production-ready Fluvio streaming service"""
    
    def __init__(self):
        self.client: Optional[Fluvio] = None
        self.producers: Dict[str, Any] = {}
        self.consumers: Dict[str, Any] = {}
        self.metrics = {
            "messages_produced": 0,
            "messages_consumed": 0,
            "errors": 0,
            "topics_created": 0
        }
        self.topics = [
            "banking.transactions",
            "banking.kyb.applications",
            "banking.kyb.documents",
            "banking.kyb.decisions",
            "banking.payments.qr",
            "banking.payments.ussd",
            "banking.payments.sms",
            "banking.payments.whatsapp",
            "banking.insurance.policies",
            "banking.insurance.claims",
            "banking.agents.performance",
            "banking.agents.onboarding",
            "banking.customers.activity",
            "banking.fraud.alerts",
            "banking.compliance.events",
            "banking.audit.logs",
            "banking.notifications",
            "banking.analytics.events",
        ]
        
    async def initialize(self) -> bool:
        """Initialize Fluvio client and create topics"""
        try:
            if not FLUVIO_AVAILABLE:
                logger.error("❌ Fluvio not available. Install with: pip install fluvio")
                return False
            
            # Connect to Fluvio cluster
            self.client = await Fluvio.connect()
            logger.info("✅ Connected to Fluvio cluster")
            
            # Get admin client
            admin = await self.client.admin()
            
            # Create topics with replication and partitions
            for topic in self.topics:
                try:
                    # Check if topic exists
                    topics_list = await admin.list_topics()
                    topic_exists = any(t.name == topic for t in topics_list)
                    
                    if not topic_exists:
                        # Create topic with replication=3, partitions=6
                        await admin.create_topic(
                            topic,
                            replication=3,
                            partitions=6,
                            ignore_rack_assignment=False
                        )
                        self.metrics["topics_created"] += 1
                        logger.info(f"✅ Created Fluvio topic: {topic} (replication=3, partitions=6)")
                    else:
                        logger.info(f"ℹ️ Topic already exists: {topic}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to create topic {topic}: {str(e)}")
                    # Continue with other topics
            
            logger.info(f"🚀 Fluvio streaming service initialized ({self.metrics['topics_created']} topics created)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Fluvio: {str(e)}")
            return False
    
    async def get_producer(self, topic: str):
        """Get or create a producer for a topic"""
        if topic not in self.producers:
            producer = await self.client.topic_producer(topic)
            self.producers[topic] = producer
            logger.info(f"✅ Created producer for topic: {topic}")
        return self.producers[topic]
    
    async def produce_event(self, topic: str, event: BankingEvent) -> bool:
        """Produce banking event to Fluvio topic"""
        try:
            # Get producer
            producer = await self.get_producer(topic)
            
            # Serialize event
            event_data = json.dumps(asdict(event))
            
            # Produce with key (for partitioning by entity_id)
            await producer.send(event.entity_id, event_data)
            
            # Flush to ensure delivery
            await producer.flush()
            
            self.metrics["messages_produced"] += 1
            logger.info(f"📤 Produced event to {topic}: {event.event_type} (entity: {event.entity_id})")
            return True
            
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"❌ Failed to produce event to {topic}: {str(e)}")
            return False
    
    async def consume_events(
        self,
        topic: str,
        partition: int,
        callback: Callable[[BankingEvent], Any],
        offset: str = "beginning"
    ) -> None:
        """Consume events from Fluvio topic"""
        try:
            # Create partition consumer
            consumer = await self.client.partition_consumer(topic, partition)
            
            # Determine offset
            if offset == "beginning":
                stream_offset = Offset.beginning()
            elif offset == "end":
                stream_offset = Offset.end()
            else:
                stream_offset = Offset.absolute(int(offset))
            
            # Start consuming
            stream = await consumer.stream(stream_offset)
            logger.info(f"🔄 Started consuming from {topic} (partition {partition}, offset {offset})")
            
            # Store consumer
            consumer_key = f"{topic}-{partition}"
            self.consumers[consumer_key] = consumer
            
            # Consume messages
            async for record in stream:
                try:
                    # Deserialize event
                    event_data = json.loads(record.value())
                    event = BankingEvent(**event_data)
                    
                    # Call callback
                    await callback(event)
                    
                    self.metrics["messages_consumed"] += 1
                    
                except Exception as e:
                    self.metrics["errors"] += 1
                    logger.error(f"❌ Error processing message: {str(e)}")
                    
        except Exception as e:
            self.metrics["errors"] += 1
            logger.error(f"❌ Failed to consume from {topic}: {str(e)}")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get streaming metrics"""
        return {
            "messages_produced": self.metrics["messages_produced"],
            "messages_consumed": self.metrics["messages_consumed"],
            "errors": self.metrics["errors"],
            "topics_created": self.metrics["topics_created"],
            "producers": len(self.producers),
            "consumers": len(self.consumers),
            "topics": self.topics
        }
    
    async def close(self):
        """Close all producers and consumers"""
        try:
            # Flush all producers
            for topic, producer in self.producers.items():
                try:
                    await producer.flush()
                    logger.info(f"✅ Flushed producer for {topic}")
                except Exception as e:
                    logger.error(f"⚠️ Error flushing producer for {topic}: {str(e)}")
            
            # Clear collections
            self.producers.clear()
            self.consumers.clear()
            
            logger.info("✅ Fluvio streaming service closed")
            
        except Exception as e:
            logger.error(f"❌ Error closing service: {str(e)}")


# ============================================================================
# FastAPI Application
# ============================================================================

# Global service instance
streaming_service: Optional[FluvioStreamingService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    global streaming_service
    
    # Startup
    logger.info("🚀 Starting Fluvio streaming service...")
    streaming_service = FluvioStreamingService()
    
    if FLUVIO_AVAILABLE:
        success = await streaming_service.initialize()
        if not success:
            logger.error("❌ Failed to initialize Fluvio service")
    else:
        logger.warning("⚠️ Fluvio not available - service running in limited mode")
    
    yield
    
    # Shutdown
    logger.info("⏹️ Shutting down Fluvio streaming service...")
    if streaming_service:
        await streaming_service.close()


app = FastAPI(
    title="Fluvio Streaming Service",
    description="Production-ready Fluvio streaming for Remittance Platform",
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
        "service": "fluvio-streaming",
        "version": "1.0.0",
        "status": "running",
        "fluvio_available": FLUVIO_AVAILABLE
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "fluvio-streaming",
        "fluvio_available": FLUVIO_AVAILABLE,
        "connected": streaming_service.client is not None if streaming_service else False
    }


@app.get("/metrics")
async def get_metrics():
    """Get streaming metrics"""
    if not streaming_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return await streaming_service.get_metrics()


@app.get("/topics")
async def list_topics():
    """List all topics"""
    if not streaming_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "topics": streaming_service.topics,
        "count": len(streaming_service.topics)
    }


@app.post("/produce/{topic}")
async def produce_event(topic: str, request: ProduceRequest):
    """Produce an event to a topic"""
    if not streaming_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not FLUVIO_AVAILABLE:
        raise HTTPException(status_code=503, detail="Fluvio not available")
    
    # Create banking event
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
    
    # Produce event
    success = await streaming_service.produce_event(topic, event)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to produce event")
    
    return {
        "status": "success",
        "event_id": event.event_id,
        "topic": topic
    }


@app.post("/consume/{topic}/{partition}")
async def start_consumer(
    topic: str,
    partition: int,
    background_tasks: BackgroundTasks,
    offset: str = "beginning"
):
    """Start consuming from a topic partition"""
    if not streaming_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not FLUVIO_AVAILABLE:
        raise HTTPException(status_code=503, detail="Fluvio not available")
    
    # Example callback (log events)
    async def log_event(event: BankingEvent):
        logger.info(f"📥 Consumed event: {event.event_type} - {event.entity_id}")
    
    # Start consumer in background
    background_tasks.add_task(
        streaming_service.consume_events,
        topic,
        partition,
        log_event,
        offset
    )
    
    return {
        "status": "started",
        "topic": topic,
        "partition": partition,
        "offset": offset
    }


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8096"))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )

