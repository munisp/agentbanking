"""
TigerBeetle to Lakehouse Sync Service
Syncs ledger postings from TigerBeetle to the lakehouse for analytics.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import struct

import asyncpg
import redis.asyncio as redis
from aiokafka import AIOKafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransferStatus(Enum):
    PENDING = "pending"
    POSTED = "posted"
    VOIDED = "voided"


@dataclass
class TigerBeetleTransfer:
    """Represents a TigerBeetle transfer/posting"""
    id: int
    debit_account_id: int
    credit_account_id: int
    amount: int
    pending_id: int
    user_data_128: int
    user_data_64: int
    user_data_32: int
    timeout: int
    ledger: int
    code: int
    flags: int
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "debit_account_id": str(self.debit_account_id),
            "credit_account_id": str(self.credit_account_id),
            "amount": self.amount,
            "pending_id": str(self.pending_id) if self.pending_id else None,
            "user_data_128": str(self.user_data_128),
            "user_data_64": str(self.user_data_64),
            "user_data_32": self.user_data_32,
            "timeout": self.timeout,
            "ledger": self.ledger,
            "code": self.code,
            "flags": self.flags,
            "timestamp": self.timestamp,
        }


@dataclass
class TigerBeetleAccount:
    """Represents a TigerBeetle account"""
    id: int
    debits_pending: int
    debits_posted: int
    credits_pending: int
    credits_posted: int
    user_data_128: int
    user_data_64: int
    user_data_32: int
    ledger: int
    code: int
    flags: int
    timestamp: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "debits_pending": self.debits_pending,
            "debits_posted": self.debits_posted,
            "credits_pending": self.credits_pending,
            "credits_posted": self.credits_posted,
            "user_data_128": str(self.user_data_128),
            "user_data_64": str(self.user_data_64),
            "user_data_32": self.user_data_32,
            "ledger": self.ledger,
            "code": self.code,
            "flags": self.flags,
            "timestamp": self.timestamp,
            "balance": self.credits_posted - self.debits_posted,
        }


class TigerBeetleLakehouseSync:
    """
    Syncs TigerBeetle ledger data to the lakehouse.
    Supports both batch sync and real-time streaming.
    """
    
    def __init__(
        self,
        tigerbeetle_addresses: str = None,
        cluster_id: int = 0,
        db_url: str = None,
        redis_url: str = None,
        kafka_brokers: str = None
    ):
        self.tigerbeetle_addresses = tigerbeetle_addresses or os.getenv(
            "TIGERBEETLE_ADDRESSES", "127.0.0.1:3000"
        )
        self.cluster_id = cluster_id
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/lakehouse"
        )
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.kafka_brokers = kafka_brokers or os.getenv("KAFKA_BROKERS", "localhost:9092")
        
        # Connections
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.kafka_producer: Optional[AIOKafkaProducer] = None
        
        # Sync state
        self.last_sync_timestamp: int = 0
        self.running = False
        
        # Metrics
        self.metrics = {
            "transfers_synced": 0,
            "accounts_synced": 0,
            "sync_errors": 0,
            "last_sync_time": None,
            "sync_latency_ms": 0,
        }
    
    async def initialize(self):
        """Initialize connections"""
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
            
            # Load last sync timestamp
            last_ts = await self.redis_client.get("tigerbeetle:last_sync_timestamp")
            if last_ts:
                self.last_sync_timestamp = int(last_ts)
            
            logger.info("Redis connected")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
        
        # Initialize Kafka producer
        try:
            self.kafka_producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
            await self.kafka_producer.start()
            logger.info("Kafka producer started")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
    
    async def _init_database(self):
        """Initialize database tables for TigerBeetle sync"""
        async with self.db_pool.acquire() as conn:
            # TigerBeetle transfers table (bronze layer)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_tigerbeetle_transfers (
                    id SERIAL PRIMARY KEY,
                    transfer_id VARCHAR(255) UNIQUE NOT NULL,
                    debit_account_id VARCHAR(255) NOT NULL,
                    credit_account_id VARCHAR(255) NOT NULL,
                    amount BIGINT NOT NULL,
                    pending_id VARCHAR(255),
                    user_data_128 VARCHAR(255),
                    user_data_64 VARCHAR(255),
                    user_data_32 INTEGER,
                    timeout INTEGER,
                    ledger INTEGER NOT NULL,
                    code INTEGER NOT NULL,
                    flags INTEGER,
                    tigerbeetle_timestamp BIGINT NOT NULL,
                    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    partition_date DATE NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tb_transfers_timestamp 
                ON lakehouse_tigerbeetle_transfers(tigerbeetle_timestamp);
                CREATE INDEX IF NOT EXISTS idx_tb_transfers_ledger 
                ON lakehouse_tigerbeetle_transfers(ledger);
                CREATE INDEX IF NOT EXISTS idx_tb_transfers_partition 
                ON lakehouse_tigerbeetle_transfers(partition_date);
            """)
            
            # TigerBeetle account snapshots table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_tigerbeetle_account_snapshots (
                    id SERIAL PRIMARY KEY,
                    account_id VARCHAR(255) NOT NULL,
                    debits_pending BIGINT NOT NULL,
                    debits_posted BIGINT NOT NULL,
                    credits_pending BIGINT NOT NULL,
                    credits_posted BIGINT NOT NULL,
                    balance BIGINT NOT NULL,
                    user_data_128 VARCHAR(255),
                    user_data_64 VARCHAR(255),
                    user_data_32 INTEGER,
                    ledger INTEGER NOT NULL,
                    code INTEGER NOT NULL,
                    flags INTEGER,
                    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    partition_date DATE NOT NULL,
                    UNIQUE(account_id, snapshot_timestamp)
                );
                CREATE INDEX IF NOT EXISTS idx_tb_accounts_id 
                ON lakehouse_tigerbeetle_account_snapshots(account_id);
                CREATE INDEX IF NOT EXISTS idx_tb_accounts_partition 
                ON lakehouse_tigerbeetle_account_snapshots(partition_date);
            """)
            
            # Sync state table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_tigerbeetle_sync_state (
                    id SERIAL PRIMARY KEY,
                    sync_type VARCHAR(50) NOT NULL,
                    last_timestamp BIGINT NOT NULL,
                    records_synced INTEGER NOT NULL,
                    sync_duration_ms INTEGER,
                    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            
            # Gold layer - daily ledger summary
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lakehouse_gold_ledger_daily (
                    id SERIAL PRIMARY KEY,
                    ledger_date DATE NOT NULL,
                    ledger_code INTEGER NOT NULL,
                    total_transfers BIGINT NOT NULL,
                    total_amount BIGINT NOT NULL,
                    unique_debit_accounts INTEGER,
                    unique_credit_accounts INTEGER,
                    avg_transfer_amount DECIMAL(18,2),
                    max_transfer_amount BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(ledger_date, ledger_code)
                );
            """)
            
            logger.info("TigerBeetle sync tables initialized")
    
    async def start_sync_loop(self, interval_seconds: int = 60):
        """Start the continuous sync loop"""
        self.running = True
        logger.info(f"Starting TigerBeetle sync loop with {interval_seconds}s interval")
        
        while self.running:
            try:
                await self.sync_transfers()
                await self.sync_account_snapshots()
                await self.update_gold_aggregates()
            except Exception as e:
                logger.error(f"Sync error: {e}")
                self.metrics["sync_errors"] += 1
            
            await asyncio.sleep(interval_seconds)
    
    async def stop(self):
        """Stop the sync loop"""
        self.running = False
        if self.kafka_producer:
            await self.kafka_producer.stop()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("TigerBeetle sync stopped")
    
    async def sync_transfers(self):
        """Sync new transfers from TigerBeetle to lakehouse"""
        start_time = datetime.utcnow()
        
        # In production, this would use the TigerBeetle client to fetch transfers
        # Read from staging table or TigerBeetle API
        transfers = await self._fetch_new_transfers()
        
        if not transfers:
            return
        
        synced_count = 0
        for transfer in transfers:
            try:
                # Write to bronze layer (database)
                await self._write_transfer_to_bronze(transfer)
                
                # Publish to Kafka for real-time processing
                await self._publish_transfer_event(transfer)
                
                synced_count += 1
                
                # Update last sync timestamp
                if transfer.timestamp > self.last_sync_timestamp:
                    self.last_sync_timestamp = transfer.timestamp
                    
            except Exception as e:
                logger.error(f"Failed to sync transfer {transfer.id}: {e}")
        
        # Save sync state
        if self.redis_client:
            await self.redis_client.set(
                "tigerbeetle:last_sync_timestamp",
                str(self.last_sync_timestamp)
            )
        
        # Update metrics
        sync_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        self.metrics["transfers_synced"] += synced_count
        self.metrics["last_sync_time"] = datetime.utcnow().isoformat()
        self.metrics["sync_latency_ms"] = sync_duration
        
        logger.info(f"Synced {synced_count} transfers in {sync_duration:.2f}ms")
    
    async def _fetch_new_transfers(self) -> List[TigerBeetleTransfer]:
        """
        Fetch new transfers from TigerBeetle.
        In production, this would use the TigerBeetle client.
        """
        # Production implementation via TigerBeetle client
        # Example: client.lookup_transfers(...)
        
        # For demonstration, we'll check if there's a staging table
        if not self.db_pool:
            return []
        
        try:
            async with self.db_pool.acquire() as conn:
                # Check for staging table with new transfers
                rows = await conn.fetch("""
                    SELECT * FROM tigerbeetle_transfer_staging
                    WHERE timestamp > $1
                    ORDER BY timestamp ASC
                    LIMIT 1000
                """, self.last_sync_timestamp)
                
                transfers = []
                for row in rows:
                    transfers.append(TigerBeetleTransfer(
                        id=row["id"],
                        debit_account_id=row["debit_account_id"],
                        credit_account_id=row["credit_account_id"],
                        amount=row["amount"],
                        pending_id=row.get("pending_id", 0),
                        user_data_128=row.get("user_data_128", 0),
                        user_data_64=row.get("user_data_64", 0),
                        user_data_32=row.get("user_data_32", 0),
                        timeout=row.get("timeout", 0),
                        ledger=row["ledger"],
                        code=row["code"],
                        flags=row.get("flags", 0),
                        timestamp=row["timestamp"],
                    ))
                
                return transfers
                
        except asyncpg.exceptions.UndefinedTableError:
            # Staging table doesn't exist - this is expected in some setups
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch transfers: {e}")
            return []
    
    async def _write_transfer_to_bronze(self, transfer: TigerBeetleTransfer):
        """Write transfer to bronze layer"""
        if not self.db_pool:
            return
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO lakehouse_tigerbeetle_transfers
                (transfer_id, debit_account_id, credit_account_id, amount, pending_id,
                 user_data_128, user_data_64, user_data_32, timeout, ledger, code, flags,
                 tigerbeetle_timestamp, partition_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (transfer_id) DO NOTHING
            """,
                str(transfer.id),
                str(transfer.debit_account_id),
                str(transfer.credit_account_id),
                transfer.amount,
                str(transfer.pending_id) if transfer.pending_id else None,
                str(transfer.user_data_128),
                str(transfer.user_data_64),
                transfer.user_data_32,
                transfer.timeout,
                transfer.ledger,
                transfer.code,
                transfer.flags,
                transfer.timestamp,
                datetime.utcnow().date()
            )
    
    async def _publish_transfer_event(self, transfer: TigerBeetleTransfer):
        """Publish transfer event to Kafka for real-time processing"""
        if not self.kafka_producer:
            return
        
        event = {
            "event_id": f"tb-{transfer.id}",
            "event_type": "ledger.posting",
            "event_version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": "tigerbeetle-sync",
            "service_version": "1.0.0",
            "correlation_id": str(transfer.user_data_128) if transfer.user_data_128 else str(transfer.id),
            "data_layer": "bronze",
            "contains_pii": False,
            "idempotency_key": f"tb-transfer-{transfer.id}",
            "payload": {
                "posting_id": str(transfer.id),
                "transaction_id": str(transfer.user_data_128) if transfer.user_data_128 else None,
                "debit_account_id": str(transfer.debit_account_id),
                "credit_account_id": str(transfer.credit_account_id),
                "amount": transfer.amount,
                "currency": "NGN",  # Default currency
                "ledger_code": transfer.ledger,
                "transfer_code": transfer.code,
                "status": "posted",
                "pending_id": str(transfer.pending_id) if transfer.pending_id else None,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }
        
        await self.kafka_producer.send_and_wait("lakehouse.ledger", event)
    
    async def sync_account_snapshots(self):
        """Sync account balance snapshots to lakehouse"""
        # In production, this would fetch account states from TigerBeetle
        # For now, we'll aggregate from the transfers we've synced
        
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Get unique accounts from recent transfers
                accounts = await conn.fetch("""
                    SELECT DISTINCT debit_account_id as account_id FROM lakehouse_tigerbeetle_transfers
                    WHERE synced_at > NOW() - INTERVAL '1 hour'
                    UNION
                    SELECT DISTINCT credit_account_id as account_id FROM lakehouse_tigerbeetle_transfers
                    WHERE synced_at > NOW() - INTERVAL '1 hour'
                """)
                
                for account in accounts:
                    account_id = account["account_id"]
                    
                    # Calculate balance from transfers
                    balance_data = await conn.fetchrow("""
                        SELECT 
                            COALESCE(SUM(CASE WHEN credit_account_id = $1 THEN amount ELSE 0 END), 0) as credits,
                            COALESCE(SUM(CASE WHEN debit_account_id = $1 THEN amount ELSE 0 END), 0) as debits
                        FROM lakehouse_tigerbeetle_transfers
                        WHERE credit_account_id = $1 OR debit_account_id = $1
                    """, account_id)
                    
                    credits = balance_data["credits"]
                    debits = balance_data["debits"]
                    balance = credits - debits
                    
                    # Insert snapshot
                    await conn.execute("""
                        INSERT INTO lakehouse_tigerbeetle_account_snapshots
                        (account_id, debits_pending, debits_posted, credits_pending, credits_posted,
                         balance, ledger, code, flags, partition_date)
                        VALUES ($1, 0, $2, 0, $3, $4, 1, 0, 0, $5)
                    """,
                        account_id,
                        debits,
                        credits,
                        balance,
                        datetime.utcnow().date()
                    )
                
                self.metrics["accounts_synced"] += len(accounts)
                logger.info(f"Synced {len(accounts)} account snapshots")
                
        except Exception as e:
            logger.error(f"Failed to sync account snapshots: {e}")
    
    async def update_gold_aggregates(self):
        """Update gold layer daily aggregates"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Aggregate daily ledger metrics
                await conn.execute("""
                    INSERT INTO lakehouse_gold_ledger_daily
                    (ledger_date, ledger_code, total_transfers, total_amount,
                     unique_debit_accounts, unique_credit_accounts, avg_transfer_amount, max_transfer_amount)
                    SELECT 
                        partition_date,
                        ledger,
                        COUNT(*),
                        SUM(amount),
                        COUNT(DISTINCT debit_account_id),
                        COUNT(DISTINCT credit_account_id),
                        AVG(amount),
                        MAX(amount)
                    FROM lakehouse_tigerbeetle_transfers
                    WHERE partition_date = CURRENT_DATE
                    GROUP BY partition_date, ledger
                    ON CONFLICT (ledger_date, ledger_code)
                    DO UPDATE SET
                        total_transfers = EXCLUDED.total_transfers,
                        total_amount = EXCLUDED.total_amount,
                        unique_debit_accounts = EXCLUDED.unique_debit_accounts,
                        unique_credit_accounts = EXCLUDED.unique_credit_accounts,
                        avg_transfer_amount = EXCLUDED.avg_transfer_amount,
                        max_transfer_amount = EXCLUDED.max_transfer_amount
                """)
                
                logger.info("Updated gold layer ledger aggregates")
                
        except Exception as e:
            logger.error(f"Failed to update gold aggregates: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get sync metrics"""
        return self.metrics.copy()


# FastAPI integration
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

sync_service: Optional[TigerBeetleLakehouseSync] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sync_service
    sync_service = TigerBeetleLakehouseSync()
    await sync_service.initialize()
    asyncio.create_task(sync_service.start_sync_loop(interval_seconds=60))
    yield
    if sync_service:
        await sync_service.stop()

app = FastAPI(
    title="TigerBeetle Lakehouse Sync",
    description="Syncs TigerBeetle ledger data to the lakehouse",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "sync_running": sync_service.running if sync_service else False
    }

@app.get("/metrics")
async def metrics():
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    return sync_service.get_metrics()

@app.post("/sync/transfers")
async def trigger_transfer_sync():
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    await sync_service.sync_transfers()
    return {"status": "completed", "metrics": sync_service.get_metrics()}

@app.post("/sync/accounts")
async def trigger_account_sync():
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    await sync_service.sync_account_snapshots()
    return {"status": "completed", "metrics": sync_service.get_metrics()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
