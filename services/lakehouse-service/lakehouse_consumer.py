"""
Lakehouse Consumer Service
Consumes banking events from Kafka/Dapr and ingests into lakehouse layers.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import asyncpg
import redis.asyncio as redis
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
try:
    from minio_storage import minio_storage, get_partition_path
    MINIO_ENABLED = True
except ImportError:
    MINIO_ENABLED = False
    logger = logging.getLogger(__name__)  # pre-init for import error path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLayer(Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class EventType(Enum):
    # Transaction events
    TRANSACTION_INITIATED = "transaction.initiated"
    TRANSACTION_AUTHORIZED = "transaction.authorized"
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_FAILED = "transaction.failed"
    TRANSACTION_REVERSED = "transaction.reversed"
    
    # Payment events
    PAYMENT_CREATED = "payment.created"
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_SETTLED = "payment.settled"
    PAYMENT_FAILED = "payment.failed"
    
    # Routing events
    ROUTING_DECISION = "routing.decision"
    ROUTING_OUTCOME = "routing.outcome"
    ROUTING_FALLBACK = "routing.fallback"
    
    # Float events
    FLOAT_ALLOCATED = "float.allocated"
    FLOAT_RELEASED = "float.released"
    FLOAT_ADJUSTED = "float.adjusted"
    FLOAT_SETTLEMENT = "float.settlement"
    
    # Commission events
    COMMISSION_CALCULATED = "commission.calculated"
    COMMISSION_ACCRUED = "commission.accrued"
    COMMISSION_SETTLED = "commission.settled"
    
    # Fraud events
    FRAUD_SCREENING = "fraud.screening"
    FRAUD_ALERT = "fraud.alert"
    FRAUD_DECISION = "fraud.decision"
    FRAUD_FEEDBACK = "fraud.feedback"
    
    # Ledger events
    LEDGER_POSTING = "ledger.posting"
    LEDGER_RESERVATION = "ledger.reservation"
    LEDGER_COMMIT = "ledger.commit"
    LEDGER_ABORT = "ledger.abort"
    
    # Mojaloop events
    MOJALOOP_QUOTE = "mojaloop.quote"
    MOJALOOP_TRANSFER = "mojaloop.transfer"
    MOJALOOP_SETTLEMENT = "mojaloop.settlement"
    
    # Agent events
    AGENT_ONBOARDED = "agent.onboarded"
    AGENT_ACTIVATED = "agent.activated"
    AGENT_SUSPENDED = "agent.suspended"
    AGENT_TRANSACTION = "agent.transaction"


# Kafka topics to consume
LAKEHOUSE_TOPICS = [
    "lakehouse.transactions",
    "lakehouse.payments",
    "lakehouse.routing",
    "lakehouse.float",
    "lakehouse.commissions",
    "lakehouse.fraud",
    "lakehouse.ledger",
    "lakehouse.mojaloop",
    "lakehouse.agents",
    "lakehouse.analytics",
    "lakehouse.ml-features",
]


@dataclass
class BankingEvent:
    event_id: str
    event_type: str
    event_version: str
    timestamp: str
    service_name: str
    service_version: str
    correlation_id: str
    causation_id: Optional[str]
    data_layer: str
    contains_pii: bool
    idempotency_key: str
    payload: Dict[str, Any]
    schema_id: Optional[str] = None
    schema_version: Optional[str] = None


@dataclass
class ProcessedEvent:
    event: BankingEvent
    layer: DataLayer
    table_name: str
    partition_key: str
    processed_at: datetime
    quality_score: float
    transformations_applied: List[str]


class LakehouseConsumer:
    """
    Consumes banking events from Kafka and ingests into lakehouse.
    Implements Bronze -> Silver -> Gold -> Platinum data flow.
    """
    
    def __init__(
        self,
        kafka_brokers: str = None,
        db_url: str = None,
        redis_url: str = None,
        data_dir: str = "/data/lakehouse"
    ):
        self.kafka_brokers = kafka_brokers or os.getenv("KAFKA_BROKERS", "localhost:9092")
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/lakehouse")
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.data_dir = data_dir
        
        # Connections
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        
        # Processing state
        self.processed_events: Dict[str, datetime] = {}  # idempotency tracking
        self.event_handlers: Dict[str, Callable] = {}
        self.running = False
        
        # Metrics
        self.metrics = {
            "events_received": 0,
            "events_processed": 0,
            "events_failed": 0,
            "events_deduplicated": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "gold_writes": 0,
            "platinum_writes": 0,
        }
        
        # Layer directories
        self.layer_dirs = {
            DataLayer.BRONZE: os.path.join(data_dir, "bronze"),
            DataLayer.SILVER: os.path.join(data_dir, "silver"),
            DataLayer.GOLD: os.path.join(data_dir, "gold"),
            DataLayer.PLATINUM: os.path.join(data_dir, "platinum"),
        }
        
        # Register default handlers
        self._register_default_handlers()
    
    async def initialize(self):
        """Initialize connections and create directories"""
        # Create directories
        for layer_dir in self.layer_dirs.values():
            os.makedirs(layer_dir, exist_ok=True)
        
        # Initialize database pool
        try:
            self.db_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=5,
                max_size=20
            )
            await self._init_database()
            logger.info("Database pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
        
        # Initialize Redis
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
        
        # Initialize Kafka consumer
        try:
            self.consumer = AIOKafkaConsumer(
                *LAKEHOUSE_TOPICS,
                bootstrap_servers=self.kafka_brokers,
                group_id="lakehouse-consumer",
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8"))
            )
            await self.consumer.start()
            logger.info(f"Kafka consumer started, subscribed to {len(LAKEHOUSE_TOPICS)} topics")
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
    
    async def _init_database(self):
        """Initialize database tables for lakehouse metadata"""
        async with self.db_pool.acquire() as conn:
            # Bronze layer events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_bronze_events (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(255) UNIQUE NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    correlation_id VARCHAR(255),
                    service_name VARCHAR(100),
                    payload JSONB NOT NULL,
                    raw_data JSONB NOT NULL,
                    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    processed_at TIMESTAMPTZ,
                    quality_score DECIMAL(5,4),
                    partition_date DATE NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bronze_event_type ON lakehouse_bronze_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_bronze_correlation ON lakehouse_bronze_events(correlation_id);
                CREATE INDEX IF NOT EXISTS idx_bronze_partition ON lakehouse_bronze_events(partition_date);
            """)
            
            # Silver layer - cleaned transactions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_silver_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(255) UNIQUE NOT NULL,
                    transaction_type VARCHAR(50),
                    amount DECIMAL(18,2),
                    currency VARCHAR(10),
                    source_account VARCHAR(100),
                    dest_account VARCHAR(100),
                    source_bank_code VARCHAR(20),
                    dest_bank_code VARCHAR(20),
                    status VARCHAR(50),
                    error_code VARCHAR(50),
                    latency_ms INTEGER,
                    agent_id VARCHAR(255),
                    channel VARCHAR(50),
                    initiated_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_silver_txn_status ON lakehouse_silver_transactions(status);
                CREATE INDEX IF NOT EXISTS idx_silver_txn_agent ON lakehouse_silver_transactions(agent_id);
                CREATE INDEX IF NOT EXISTS idx_silver_txn_date ON lakehouse_silver_transactions(initiated_at);
            """)
            
            # Silver layer - cleaned routing decisions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_silver_routing (
                    id SERIAL PRIMARY KEY,
                    transfer_id VARCHAR(255) NOT NULL,
                    source_bank_code VARCHAR(20),
                    dest_bank_code VARCHAR(20),
                    amount DECIMAL(18,2),
                    selected_rail VARCHAR(50),
                    score DECIMAL(10,6),
                    predicted_success_rate DECIMAL(5,4),
                    predicted_latency_ms INTEGER,
                    predicted_cost DECIMAL(10,2),
                    actual_successful BOOLEAN,
                    actual_latency_ms INTEGER,
                    actual_cost DECIMAL(10,2),
                    model_version VARCHAR(50),
                    decision_timestamp TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_silver_routing_bank ON lakehouse_silver_routing(dest_bank_code);
                CREATE INDEX IF NOT EXISTS idx_silver_routing_rail ON lakehouse_silver_routing(selected_rail);
            """)
            
            # Silver layer - cleaned float events
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_silver_float (
                    id SERIAL PRIMARY KEY,
                    float_id VARCHAR(255) NOT NULL,
                    agent_id VARCHAR(255),
                    bank_code VARCHAR(20),
                    operation_type VARCHAR(50),
                    amount DECIMAL(18,2),
                    balance_before DECIMAL(18,2),
                    balance_after DECIMAL(18,2),
                    daily_limit DECIMAL(18,2),
                    daily_used DECIMAL(18,2),
                    risk_score DECIMAL(5,4),
                    event_timestamp TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_silver_float_agent ON lakehouse_silver_float(agent_id);
            """)
            
            # Silver layer - cleaned ledger postings
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_silver_ledger (
                    id SERIAL PRIMARY KEY,
                    posting_id VARCHAR(255) UNIQUE NOT NULL,
                    transaction_id VARCHAR(255),
                    debit_account_id VARCHAR(255),
                    credit_account_id VARCHAR(255),
                    amount BIGINT,
                    currency VARCHAR(10),
                    ledger_code INTEGER,
                    transfer_code INTEGER,
                    status VARCHAR(50),
                    event_timestamp TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_silver_ledger_txn ON lakehouse_silver_ledger(transaction_id);
            """)
            
            # Gold layer - aggregated metrics
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_gold_daily_metrics (
                    id SERIAL PRIMARY KEY,
                    metric_date DATE NOT NULL,
                    metric_type VARCHAR(100) NOT NULL,
                    dimension_key VARCHAR(255),
                    dimension_value VARCHAR(255),
                    total_count BIGINT,
                    total_amount DECIMAL(18,2),
                    success_count BIGINT,
                    failure_count BIGINT,
                    avg_latency_ms DECIMAL(10,2),
                    p50_latency_ms DECIMAL(10,2),
                    p95_latency_ms DECIMAL(10,2),
                    p99_latency_ms DECIMAL(10,2),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(metric_date, metric_type, dimension_key, dimension_value)
                );
                CREATE INDEX IF NOT EXISTS idx_gold_metrics_date ON lakehouse_gold_daily_metrics(metric_date);
                CREATE INDEX IF NOT EXISTS idx_gold_metrics_type ON lakehouse_gold_daily_metrics(metric_type);
            """)
            
            # Platinum layer - ML features
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_platinum_routing_features (
                    id SERIAL PRIMARY KEY,
                    feature_date DATE NOT NULL,
                    bank_code VARCHAR(20) NOT NULL,
                    rail VARCHAR(50) NOT NULL,
                    hour_of_day INTEGER,
                    success_rate_1h DECIMAL(5,4),
                    success_rate_24h DECIMAL(5,4),
                    success_rate_7d DECIMAL(5,4),
                    avg_latency_1h DECIMAL(10,2),
                    avg_latency_24h DECIMAL(10,2),
                    transaction_count_1h INTEGER,
                    transaction_count_24h INTEGER,
                    avg_amount DECIMAL(18,2),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(feature_date, bank_code, rail, hour_of_day)
                );
                CREATE INDEX IF NOT EXISTS idx_platinum_features_bank ON lakehouse_platinum_routing_features(bank_code);
            """)
            
            # Platinum layer - fraud features
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_platinum_fraud_features (
                    id SERIAL PRIMARY KEY,
                    feature_date DATE NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id VARCHAR(255) NOT NULL,
                    transaction_count_1h INTEGER,
                    transaction_count_24h INTEGER,
                    transaction_volume_1h DECIMAL(18,2),
                    transaction_volume_24h DECIMAL(18,2),
                    unique_counterparties_24h INTEGER,
                    avg_transaction_amount DECIMAL(18,2),
                    max_transaction_amount DECIMAL(18,2),
                    velocity_score DECIMAL(5,4),
                    anomaly_score DECIMAL(5,4),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(feature_date, entity_type, entity_id)
                );
                CREATE INDEX IF NOT EXISTS idx_platinum_fraud_entity ON lakehouse_platinum_fraud_features(entity_type, entity_id);
            """)
            
            logger.info("Database tables initialized")
    
    def _register_default_handlers(self):
        """Register default event handlers"""
        # Transaction handlers
        self.event_handlers["transaction.initiated"] = self._handle_transaction_event
        self.event_handlers["transaction.authorized"] = self._handle_transaction_event
        self.event_handlers["transaction.completed"] = self._handle_transaction_event
        self.event_handlers["transaction.failed"] = self._handle_transaction_event
        self.event_handlers["transaction.reversed"] = self._handle_transaction_event
        
        # Routing handlers
        self.event_handlers["routing.decision"] = self._handle_routing_event
        self.event_handlers["routing.outcome"] = self._handle_routing_event
        
        # Float handlers
        self.event_handlers["float.allocated"] = self._handle_float_event
        self.event_handlers["float.released"] = self._handle_float_event
        self.event_handlers["float.adjusted"] = self._handle_float_event
        
        # Ledger handlers
        self.event_handlers["ledger.posting"] = self._handle_ledger_event
        self.event_handlers["ledger.reservation"] = self._handle_ledger_event
        self.event_handlers["ledger.commit"] = self._handle_ledger_event
        
        # Fraud handlers
        self.event_handlers["fraud.screening"] = self._handle_fraud_event
        self.event_handlers["fraud.decision"] = self._handle_fraud_event
        
        # Mojaloop handlers
        self.event_handlers["mojaloop.quote"] = self._handle_mojaloop_event
        self.event_handlers["mojaloop.transfer"] = self._handle_mojaloop_event
        self.event_handlers["mojaloop.settlement"] = self._handle_mojaloop_event
        
        # Commission handlers
        self.event_handlers["commission.calculated"] = self._handle_commission_event
        self.event_handlers["commission.settled"] = self._handle_commission_event
        
        # Agent handlers
        self.event_handlers["agent.onboarded"] = self._handle_agent_event
        self.event_handlers["agent.transaction"] = self._handle_agent_event
    
    async def start(self):
        """Start consuming events"""
        self.running = True
        logger.info("Starting lakehouse consumer...")
        
        while self.running:
            try:
                async for message in self.consumer:
                    await self._process_message(message)
                    await self.consumer.commit()
            except KafkaError as e:
                logger.error(f"Kafka error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the consumer"""
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Lakehouse consumer stopped")
    
    async def _process_message(self, message):
        """Process a single Kafka message"""
        self.metrics["events_received"] += 1
        
        try:
            event_data = message.value
            event = BankingEvent(
                event_id=event_data.get("event_id"),
                event_type=event_data.get("event_type"),
                event_version=event_data.get("event_version", "1.0"),
                timestamp=event_data.get("timestamp"),
                service_name=event_data.get("service_name"),
                service_version=event_data.get("service_version"),
                correlation_id=event_data.get("correlation_id"),
                causation_id=event_data.get("causation_id"),
                data_layer=event_data.get("data_layer", "bronze"),
                contains_pii=event_data.get("contains_pii", False),
                idempotency_key=event_data.get("idempotency_key"),
                payload=event_data.get("payload", {}),
                schema_id=event_data.get("schema_id"),
                schema_version=event_data.get("schema_version"),
            )
            
            # Check idempotency
            if await self._is_duplicate(event.idempotency_key):
                self.metrics["events_deduplicated"] += 1
                logger.debug(f"Duplicate event skipped: {event.event_id}")
                return
            
            # Write to bronze layer (raw)
            await self._write_bronze(event, event_data)
            
            # Process through handler
            handler = self.event_handlers.get(event.event_type)
            if handler:
                await handler(event)
            else:
                logger.warning(f"No handler for event type: {event.event_type}")
            
            # Mark as processed
            await self._mark_processed(event.idempotency_key)
            self.metrics["events_processed"] += 1
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            self.metrics["events_failed"] += 1
    
    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if event was already processed"""
        if self.redis_client:
            exists = await self.redis_client.exists(f"lakehouse:processed:{idempotency_key}")
            return exists > 0
        return idempotency_key in self.processed_events
    
    async def _mark_processed(self, idempotency_key: str):
        """Mark event as processed"""
        if self.redis_client:
            await self.redis_client.setex(
                f"lakehouse:processed:{idempotency_key}",
                86400 * 7,  # 7 days TTL
                "1"
            )
        else:
            self.processed_events[idempotency_key] = datetime.utcnow()
    
    async def _write_bronze(self, event: BankingEvent, raw_data: Dict):
        """Write raw event to bronze layer (PostgreSQL + MinIO Parquet)"""
        if not self.db_pool:
            return

        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_bronze_events
                (event_id, event_type, correlation_id, service_name, payload, raw_data, partition_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (event_id) DO NOTHING
            """,
                event.event_id,
                event.event_type,
                event.correlation_id,
                event.service_name,
                json.dumps(event.payload),
                json.dumps(raw_data),
                datetime.utcnow().date()
            )

        # ── Upload raw event as Parquet to MinIO bronze bucket ────────────────
        if MINIO_ENABLED:
            try:
                now = datetime.utcnow()
                df = pd.DataFrame([{
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "correlation_id": event.correlation_id,
                    "service_name": event.service_name,
                    "payload": json.dumps(event.payload),
                    "raw_data": json.dumps(raw_data),
                    "ingested_at": now.isoformat(),
                }])
                table = pa.Table.from_pandas(df)
                buf = pa.BufferOutputStream()
                pq.write_table(table, buf, compression="snappy")
                parquet_bytes = buf.getvalue().to_pybytes()
                partition_path = get_partition_path(
                    "bronze",
                    event.event_type.replace(".", "/"),
                    now,
                    event.event_id[:8],
                )
                minio_storage.upload_parquet("bronze", partition_path, parquet_bytes)
            except Exception as minio_err:
                logger.warning(f"MinIO bronze upload failed (non-fatal): {minio_err}")

        self.metrics["bronze_writes"] += 1
    
    async def _handle_transaction_event(self, event: BankingEvent):
        """Handle transaction events - write to silver layer"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_silver_transactions
                (transaction_id, transaction_type, amount, currency, source_account, dest_account,
                 source_bank_code, dest_bank_code, status, error_code, latency_ms, agent_id,
                 channel, initiated_at, completed_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (transaction_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    error_code = EXCLUDED.error_code,
                    latency_ms = EXCLUDED.latency_ms,
                    completed_at = EXCLUDED.completed_at
            """,
                payload.get("transaction_id"),
                payload.get("transaction_type"),
                payload.get("amount"),
                payload.get("currency"),
                payload.get("source_account"),
                payload.get("dest_account"),
                payload.get("source_bank_code"),
                payload.get("dest_bank_code"),
                payload.get("status"),
                payload.get("error_code"),
                payload.get("latency_ms"),
                payload.get("agent_id"),
                payload.get("channel"),
                payload.get("initiated_at"),
                payload.get("completed_at")
            )
        
        self.metrics["silver_writes"] += 1
        
        # Trigger gold aggregation if transaction completed
        if event.event_type in ["transaction.completed", "transaction.failed"]:
            await self._update_gold_metrics("transaction", payload)
    
    async def _handle_routing_event(self, event: BankingEvent):
        """Handle routing events - write to silver layer"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_silver_routing
                (transfer_id, source_bank_code, dest_bank_code, amount, selected_rail, score,
                 predicted_success_rate, predicted_latency_ms, predicted_cost, actual_successful,
                 actual_latency_ms, actual_cost, model_version, decision_timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT DO NOTHING
            """,
                payload.get("transfer_id"),
                payload.get("source_bank_code"),
                payload.get("dest_bank_code"),
                payload.get("amount"),
                payload.get("selected_rail"),
                payload.get("score"),
                payload.get("predicted_success_rate"),
                payload.get("predicted_latency_ms"),
                payload.get("predicted_cost"),
                payload.get("actual_successful"),
                payload.get("actual_latency_ms"),
                payload.get("actual_cost"),
                payload.get("model_version"),
                payload.get("decision_timestamp")
            )
        
        self.metrics["silver_writes"] += 1
        
        # Update platinum ML features
        if event.event_type == "routing.outcome":
            await self._update_routing_features(payload)
    
    async def _handle_float_event(self, event: BankingEvent):
        """Handle float events - write to silver layer"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_silver_float
                (float_id, agent_id, bank_code, operation_type, amount, balance_before,
                 balance_after, daily_limit, daily_used, risk_score, event_timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                payload.get("float_id"),
                payload.get("agent_id"),
                payload.get("bank_code"),
                payload.get("operation_type"),
                payload.get("amount"),
                payload.get("balance_before"),
                payload.get("balance_after"),
                payload.get("daily_limit"),
                payload.get("daily_used"),
                payload.get("risk_score"),
                payload.get("timestamp")
            )
        
        self.metrics["silver_writes"] += 1
    
    async def _handle_ledger_event(self, event: BankingEvent):
        """Handle ledger events - write to silver layer"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_silver_ledger
                (posting_id, transaction_id, debit_account_id, credit_account_id, amount,
                 currency, ledger_code, transfer_code, status, event_timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (posting_id) DO UPDATE SET
                    status = EXCLUDED.status
            """,
                payload.get("posting_id"),
                payload.get("transaction_id"),
                payload.get("debit_account_id"),
                payload.get("credit_account_id"),
                payload.get("amount"),
                payload.get("currency"),
                payload.get("ledger_code"),
                payload.get("transfer_code"),
                payload.get("status"),
                payload.get("timestamp")
            )
        
        self.metrics["silver_writes"] += 1
    
    async def _handle_fraud_event(self, event: BankingEvent):
        """Handle fraud events - update platinum features"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        # Update fraud features in platinum layer
        await self._update_fraud_features(payload)
        self.metrics["platinum_writes"] += 1
    
    async def _handle_mojaloop_event(self, event: BankingEvent):
        """Handle Mojaloop events"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        # Write to bronze (already done) and update gold metrics
        await self._update_gold_metrics("mojaloop", payload)
    
    async def _handle_commission_event(self, event: BankingEvent):
        """Handle commission events"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        await self._update_gold_metrics("commission", payload)
    
    async def _handle_agent_event(self, event: BankingEvent):
        """Handle agent events"""
        payload = event.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        await self._update_gold_metrics("agent", payload)
    
    async def _update_gold_metrics(self, metric_type: str, payload: Dict):
        """Update gold layer aggregated metrics"""
        if not self.db_pool:
            return
        
        today = datetime.utcnow().date()
        
        async with self.db_pool.acquire() as conn:
            if metric_type == "transaction":
                # Update transaction metrics by bank
                await conn.execute("""
                    INSERT INTO lakehouse_gold_daily_metrics
                    (metric_date, metric_type, dimension_key, dimension_value, total_count, total_amount,
                     success_count, failure_count, avg_latency_ms)
                    VALUES ($1, 'transaction_by_bank', 'dest_bank_code', $2, 1, $3,
                            CASE WHEN $4 = 'completed' THEN 1 ELSE 0 END,
                            CASE WHEN $4 = 'failed' THEN 1 ELSE 0 END,
                            $5)
                    ON CONFLICT (metric_date, metric_type, dimension_key, dimension_value)
                    DO UPDATE SET
                        total_count = lakehouse_gold_daily_metrics.total_count + 1,
                        total_amount = lakehouse_gold_daily_metrics.total_amount + EXCLUDED.total_amount,
                        success_count = lakehouse_gold_daily_metrics.success_count + EXCLUDED.success_count,
                        failure_count = lakehouse_gold_daily_metrics.failure_count + EXCLUDED.failure_count
                """,
                    today,
                    payload.get("dest_bank_code"),
                    payload.get("amount", 0),
                    payload.get("status"),
                    payload.get("latency_ms", 0)
                )
        
        self.metrics["gold_writes"] += 1
    
    async def _update_routing_features(self, payload: Dict):
        """Update platinum layer routing features"""
        if not self.db_pool:
            return
        
        today = datetime.utcnow().date()
        hour = datetime.utcnow().hour
        
        async with self.db_pool.acquire() as conn:
            # Get recent success rates
            success_rate_1h = await conn.fetchval("""
                SELECT AVG(CASE WHEN actual_successful THEN 1.0 ELSE 0.0 END)
                FROM lakehouse_silver_routing
                WHERE dest_bank_code = $1 AND selected_rail = $2
                AND decision_timestamp > NOW() - INTERVAL '1 hour'
            """, payload.get("dest_bank_code"), payload.get("selected_rail"))
            
            success_rate_24h = await conn.fetchval("""
                SELECT AVG(CASE WHEN actual_successful THEN 1.0 ELSE 0.0 END)
                FROM lakehouse_silver_routing
                WHERE dest_bank_code = $1 AND selected_rail = $2
                AND decision_timestamp > NOW() - INTERVAL '24 hours'
            """, payload.get("dest_bank_code"), payload.get("selected_rail"))
            
            # Insert/update features
            await conn.execute("""
                INSERT INTO lakehouse_platinum_routing_features
                (feature_date, bank_code, rail, hour_of_day, success_rate_1h, success_rate_24h)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (feature_date, bank_code, rail, hour_of_day)
                DO UPDATE SET
                    success_rate_1h = EXCLUDED.success_rate_1h,
                    success_rate_24h = EXCLUDED.success_rate_24h
            """,
                today,
                payload.get("dest_bank_code"),
                payload.get("selected_rail"),
                hour,
                success_rate_1h or 0.95,
                success_rate_24h or 0.95
            )
        
        self.metrics["platinum_writes"] += 1
    
    async def _update_fraud_features(self, payload: Dict):
        """Update platinum layer fraud features"""
        if not self.db_pool:
            return
        
        today = datetime.utcnow().date()
        entity_type = "customer" if payload.get("customer_id") else "agent"
        entity_id = payload.get("customer_id") or payload.get("agent_id")
        
        if not entity_id:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_platinum_fraud_features
                (feature_date, entity_type, entity_id, anomaly_score)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (feature_date, entity_type, entity_id)
                DO UPDATE SET
                    anomaly_score = EXCLUDED.anomaly_score
            """,
                today,
                entity_type,
                entity_id,
                payload.get("risk_score", 0)
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        return self.metrics.copy()


# FastAPI integration
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

consumer: Optional[LakehouseConsumer] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer
    consumer = LakehouseConsumer()
    await consumer.initialize()
    asyncio.create_task(consumer.start())
    yield
    if consumer:
        await consumer.stop()

app = FastAPI(
    title="Lakehouse Consumer Service",
    description="Consumes banking events and ingests into lakehouse",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    return {"status": "healthy", "consumer_running": consumer.running if consumer else False}

@app.get("/metrics")
async def metrics():
    if not consumer:
        raise HTTPException(status_code=503, detail="Consumer not initialized")
    return consumer.get_metrics()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)
