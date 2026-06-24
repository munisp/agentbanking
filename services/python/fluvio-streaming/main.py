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
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel, Field
import uvicorn

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/fluvio_streaming")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
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
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("root", "fluvio-streaming")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

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
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("list_topics", "fluvio-streaming")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    if not streaming_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "topics": streaming_service.topics,
        "count": len(streaming_service.topics)
    }

@app.post("/produce/{topic}")
async def produce_event(topic: str, request: ProduceRequest):
    """Produce an event to a topic"""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("produce_event_" + str(int(_time.time() * 1000)), _json.dumps({"action": "produce_event", "timestamp": _time.time()}), "fluvio-streaming")

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

