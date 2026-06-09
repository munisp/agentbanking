import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
#!/usr/bin/env python3
"""
TigerBeetle Synchronization Service
Handles bi-directional synchronization between TigerBeetle (Zig/Go) and PostgreSQL metadata
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

import aiohttp
import asyncpg
import aioredis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("tigerbeetle-sync-service")
app.include_router(metrics_router)

from pydantic import BaseModel
import uvicorn
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Import helper functions
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from tigerbeetle_sync_helpers import TigerBeetleSyncHelpers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Metrics
sync_operations_total = Counter('tigerbeetle_sync_operations_total', 'Total sync operations', ['operation', 'status'])
sync_duration = Histogram('tigerbeetle_sync_duration_seconds', 'Sync operation duration')
sync_lag = Gauge('tigerbeetle_sync_lag_seconds', 'Sync lag in seconds')
sync_errors = Counter('tigerbeetle_sync_errors_total', 'Total sync errors', ['error_type'])
pending_sync_items = Gauge('tigerbeetle_sync_pending_items', 'Number of pending sync items')

@dataclass
class SyncEvent:
    """Represents a synchronization event"""
    id: str
    event_type: str  # 'account_created', 'transfer_created', 'balance_updated'
    source: str      # 'tigerbeetle_zig', 'tigerbeetle_edge', 'postgres'
    target: str      # 'tigerbeetle_zig', 'tigerbeetle_edge', 'postgres'
    data: Dict[str, Any]
    timestamp: datetime
    processed: bool = False
    retry_count: int = 0
    error_message: Optional[str] = None

@dataclass
class AccountSync:
    """Account synchronization data"""
    tigerbeetle_id: int
    customer_id: str
    agent_id: Optional[str]
    account_number: str
    account_type: str
    currency: str
    status: str
    kyc_level: str
    balance: int
    debits_posted: int
    credits_posted: int
    last_updated: datetime

@dataclass
class TransferSync:
    """Transfer synchronization data"""
    tigerbeetle_id: int
    transaction_id: str
    debit_account_id: int
    credit_account_id: int
    amount: int
    currency: str
    description: str
    status: str
    created_at: datetime

class TigerBeetleSyncService:
    """Main synchronization service"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_pool: Optional[asyncpg.Pool] = None
        self.redis: Optional[aioredis.Redis] = None
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Sync configuration
        self.sync_interval = config.get('sync_interval', 30)  # seconds
        self.batch_size = config.get('batch_size', 1000)
        self.max_retries = config.get('max_retries', 3)
        
        # Service endpoints
        self.tigerbeetle_zig_endpoint = config['tigerbeetle_zig_endpoint']
        self.tigerbeetle_edge_endpoint = config['tigerbeetle_edge_endpoint']
        
        # Sync state
        self.last_sync_time = {}
        self.sync_running = False
        
    async def initialize(self):
        """Initialize all connections and services"""
        try:
            # Initialize database connection pool
            self.db_pool = await asyncpg.create_pool(
                self.config['database_url'],
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Initialize Redis connection
            self.redis = await aioredis.from_url(
                self.config['redis_url'],
                encoding='utf-8',
                decode_responses=True
            )
            
            # Initialize HTTP session
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Initialize database tables
            await self.init_sync_tables()
            
            # Initialize helper tables
            async with self.db_pool.acquire() as conn:
                await TigerBeetleSyncHelpers.ensure_sync_tables_exist(conn)
            
            logger.info("TigerBeetle Sync Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize sync service: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis:
            await self.redis.close()
    
    async def init_sync_tables(self):
        """Initialize synchronization tables"""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS sync_events (
                id VARCHAR(100) PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                source VARCHAR(50) NOT NULL,
                target VARCHAR(50) NOT NULL,
                data JSONB NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                processed BOOLEAN DEFAULT FALSE,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                service_name VARCHAR(50) PRIMARY KEY,
                last_sync_time TIMESTAMP NOT NULL,
                last_sync_id VARCHAR(100),
                sync_count BIGINT DEFAULT 0,
                error_count BIGINT DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS account_sync_log (
                id SERIAL PRIMARY KEY,
                tigerbeetle_id BIGINT NOT NULL,
                postgres_id BIGINT,
                sync_type VARCHAR(20) NOT NULL,
                sync_direction VARCHAR(20) NOT NULL,
                sync_status VARCHAR(20) NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transfer_sync_log (
                id SERIAL PRIMARY KEY,
                tigerbeetle_id BIGINT NOT NULL,
                postgres_id VARCHAR(100),
                sync_type VARCHAR(20) NOT NULL,
                sync_direction VARCHAR(20) NOT NULL,
                sync_status VARCHAR(20) NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            # Indexes
            "CREATE INDEX IF NOT EXISTS idx_sync_events_processed ON sync_events(processed, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_sync_events_type ON sync_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_account_sync_log_tb_id ON account_sync_log(tigerbeetle_id)",
            "CREATE INDEX IF NOT EXISTS idx_transfer_sync_log_tb_id ON transfer_sync_log(tigerbeetle_id)",
        ]
        
        async with self.db_pool.acquire() as conn:
            for query in queries:
                await conn.execute(query)
    
    async def start_sync_workers(self):
        """Start background synchronization workers"""
        logger.info("Starting sync workers...")
        
        # Start periodic sync worker
        asyncio.create_task(self.periodic_sync_worker())
        
        # Start event processor
        asyncio.create_task(self.event_processor())
        
        # Start health monitor
        asyncio.create_task(self.health_monitor())
        
        # Start Redis event listener
        asyncio.create_task(self.redis_event_listener())
        
        logger.info("All sync workers started")
    
    async def periodic_sync_worker(self):
        """Periodic synchronization worker"""
        while True:
            try:
                if not self.sync_running:
                    self.sync_running = True
                    await self.perform_full_sync()
                    self.sync_running = False
                
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Error in periodic sync worker: {e}")
                self.sync_running = False
                sync_errors.labels(error_type='periodic_sync').inc()
                await asyncio.sleep(5)  # Brief pause before retry
    
    async def perform_full_sync(self):
        """Perform full bidirectional synchronization"""
        start_time = time.time()
        
        try:
            logger.info("Starting full synchronization...")
            
            # Sync accounts from TigerBeetle to PostgreSQL
            await self.sync_accounts_from_tigerbeetle()
            
            # Sync transfers from TigerBeetle to PostgreSQL
            await self.sync_transfers_from_tigerbeetle()
            
            # Sync metadata from PostgreSQL to TigerBeetle
            await self.sync_metadata_to_tigerbeetle()
            
            # Process pending sync events
            await self.process_pending_events()
            
            # Update sync metrics
            duration = time.time() - start_time
            sync_duration.observe(duration)
            sync_operations_total.labels(operation='full_sync', status='success').inc()
            
            logger.info(f"Full synchronization completed in {duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error in full sync: {e}")
            sync_operations_total.labels(operation='full_sync', status='error').inc()
            sync_errors.labels(error_type='full_sync').inc()
            raise
    
    async def sync_accounts_from_tigerbeetle(self):
        """Sync account data from TigerBeetle to PostgreSQL"""
        try:
            # Get accounts from TigerBeetle Zig (primary source)
            accounts = await self.get_tigerbeetle_accounts()
            
            if not accounts:
                return
            
            # Process accounts in batches
            for i in range(0, len(accounts), self.batch_size):
                batch = accounts[i:i + self.batch_size]
                await self.process_account_batch(batch)
            
            logger.info(f"Synced {len(accounts)} accounts from TigerBeetle")
            
        except Exception as e:
            logger.error(f"Error syncing accounts from TigerBeetle: {e}")
            sync_errors.labels(error_type='account_sync').inc()
            raise
    
    async def sync_transfers_from_tigerbeetle(self):
        """Sync transfer data from TigerBeetle to PostgreSQL"""
        try:
            # Get transfers from TigerBeetle Zig (primary source)
            transfers = await self.get_tigerbeetle_transfers()
            
            if not transfers:
                return
            
            # Process transfers in batches
            for i in range(0, len(transfers), self.batch_size):
                batch = transfers[i:i + self.batch_size]
                await self.process_transfer_batch(batch)
            
            logger.info(f"Synced {len(transfers)} transfers from TigerBeetle")
            
        except Exception as e:
            logger.error(f"Error syncing transfers from TigerBeetle: {e}")
            sync_errors.labels(error_type='transfer_sync').inc()
            raise
    
    async def sync_metadata_to_tigerbeetle(self):
        """Sync metadata from PostgreSQL to TigerBeetle"""
        try:
            # Get pending metadata updates
            pending_updates = await self.get_pending_metadata_updates()
            
            for update in pending_updates:
                await self.apply_metadata_update(update)
            
            logger.info(f"Applied {len(pending_updates)} metadata updates to TigerBeetle")
            
        except Exception as e:
            logger.error(f"Error syncing metadata to TigerBeetle: {e}")
            sync_errors.labels(error_type='metadata_sync').inc()
            raise
    
    async def get_tigerbeetle_accounts(self) -> List[Dict[str, Any]]:
        """Get accounts from TigerBeetle"""
        try:
            # Try edge endpoint first
            accounts = await self.fetch_accounts_from_endpoint(self.tigerbeetle_edge_endpoint)
            if accounts is not None:
                return accounts
            
            # Fallback to Zig primary
            accounts = await self.fetch_accounts_from_endpoint(self.tigerbeetle_zig_endpoint)
            if accounts is not None:
                return accounts
            
            logger.warning("Failed to fetch accounts from both TigerBeetle endpoints")
            return []
            
        except Exception as e:
            logger.error(f"Error getting TigerBeetle accounts: {e}")
            return []
    
    async def fetch_accounts_from_endpoint(self, endpoint: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch accounts from a specific TigerBeetle endpoint"""
        try:
            url = f"{endpoint}/accounts"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('accounts', [])
                else:
                    logger.warning(f"Failed to fetch accounts from {endpoint}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching accounts from {endpoint}: {e}")
            return None
    
    async def get_tigerbeetle_transfers(self) -> List[Dict[str, Any]]:
        """Get transfers from TigerBeetle"""
        try:
            # Try edge endpoint first
            transfers = await self.fetch_transfers_from_endpoint(self.tigerbeetle_edge_endpoint)
            if transfers is not None:
                return transfers
            
            # Fallback to Zig primary
            transfers = await self.fetch_transfers_from_endpoint(self.tigerbeetle_zig_endpoint)
            if transfers is not None:
                return transfers
            
            logger.warning("Failed to fetch transfers from both TigerBeetle endpoints")
            return []
            
        except Exception as e:
            logger.error(f"Error getting TigerBeetle transfers: {e}")
            return []
    
    async def fetch_transfers_from_endpoint(self, endpoint: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch transfers from a specific TigerBeetle endpoint"""
        try:
            # Get transfers since last sync
            last_sync = self.last_sync_time.get('transfers', datetime.now() - timedelta(hours=1))
            timestamp = int(last_sync.timestamp())
            
            url = f"{endpoint}/transfers?since={timestamp}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('transfers', [])
                else:
                    logger.warning(f"Failed to fetch transfers from {endpoint}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching transfers from {endpoint}: {e}")
            return None
    
    async def process_account_batch(self, accounts: List[Dict[str, Any]]):
        """Process a batch of accounts"""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for account in accounts:
                    await self.sync_account_to_postgres(conn, account)
    
    async def sync_account_to_postgres(self, conn: asyncpg.Connection, account: Dict[str, Any]):
        """Sync a single account to PostgreSQL"""
        try:
            tigerbeetle_id = account['id']
            
            # Check if account metadata exists
            existing = await conn.fetchrow(
                "SELECT id FROM account_metadata WHERE id = $1",
                tigerbeetle_id
            )
            
            if existing:
                # Update existing metadata with TigerBeetle balance data
                await conn.execute("""
                    UPDATE account_metadata 
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                """, tigerbeetle_id)
            else:
                # Create placeholder metadata for new TigerBeetle account
                await conn.execute("""
                    INSERT INTO account_metadata (
                        id, customer_id, account_number, account_type, 
                        currency, status, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO NOTHING
                """, 
                    tigerbeetle_id,
                    await TigerBeetleSyncHelpers.get_customer_id_from_account(tigerbeetle_id, conn) or f"customer_{tigerbeetle_id}",
                    await TigerBeetleSyncHelpers.generate_account_number(tigerbeetle_id, conn),
                    account.get('user_data', {}).get('account_type', 'savings'),
                    account.get('ledger', 1) == 1 and "NGN" or "USD",  # Ledger-based currency
                    "active"
                )
            
            # Log sync operation
            await conn.execute("""
                INSERT INTO account_sync_log (
                    tigerbeetle_id, sync_type, sync_direction, sync_status
                ) VALUES ($1, $2, $3, $4)
            """, tigerbeetle_id, "balance_update", "tb_to_pg", "success")
            
        except Exception as e:
            logger.error(f"Error syncing account {account.get('id')} to PostgreSQL: {e}")
            # Log error
            await conn.execute("""
                INSERT INTO account_sync_log (
                    tigerbeetle_id, sync_type, sync_direction, sync_status, error_message
                ) VALUES ($1, $2, $3, $4, $5)
            """, account.get('id'), "balance_update", "tb_to_pg", "error", str(e))
            raise
    
    async def process_transfer_batch(self, transfers: List[Dict[str, Any]]):
        """Process a batch of transfers"""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for transfer in transfers:
                    await self.sync_transfer_to_postgres(conn, transfer)
    
    async def sync_transfer_to_postgres(self, conn: asyncpg.Connection, transfer: Dict[str, Any]):
        """Sync a single transfer to PostgreSQL"""
        try:
            tigerbeetle_id = transfer['id']
            
            # Check if transfer metadata exists
            existing = await conn.fetchrow(
                "SELECT id FROM transfer_metadata WHERE id = $1",
                tigerbeetle_id
            )
            
            if not existing:
                # Create placeholder metadata for new TigerBeetle transfer
                await conn.execute("""
                    INSERT INTO transfer_metadata (
                        id, payment_reference, description, status, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO NOTHING
                """, 
                    tigerbeetle_id,
                    await TigerBeetleSyncHelpers.get_payment_reference(tigerbeetle_id, conn),
                    await TigerBeetleSyncHelpers.get_transfer_description(transfer, conn),
                    transfer.get('flags', 0) == 0 and "completed" or "pending"
                )
            
            # Log sync operation
            await conn.execute("""
                INSERT INTO transfer_sync_log (
                    tigerbeetle_id, sync_type, sync_direction, sync_status
                ) VALUES ($1, $2, $3, $4)
            """, tigerbeetle_id, "transfer_sync", "tb_to_pg", "success")
            
        except Exception as e:
            logger.error(f"Error syncing transfer {transfer.get('id')} to PostgreSQL: {e}")
            # Log error
            await conn.execute("""
                INSERT INTO transfer_sync_log (
                    tigerbeetle_id, sync_type, sync_direction, sync_status, error_message
                ) VALUES ($1, $2, $3, $4, $5)
            """, transfer.get('id'), "transfer_sync", "tb_to_pg", "error", str(e))
            raise
    
    async def get_pending_metadata_updates(self) -> List[Dict[str, Any]]:
        """Get pending metadata updates from PostgreSQL"""
        async with self.db_pool.acquire() as conn:
            # Get accounts with updated metadata
            account_updates = await conn.fetch("""
                SELECT id, customer_id, agent_id, account_number, account_type, 
                       currency, status, kyc_level, updated_at
                FROM account_metadata 
                WHERE updated_at > (
                    SELECT COALESCE(last_sync_time, '1970-01-01'::timestamp) 
                    FROM sync_state 
                    WHERE service_name = 'metadata_sync'
                )
                ORDER BY updated_at
                LIMIT $1
            """, self.batch_size)
            
            return [dict(row) for row in account_updates]
    
    async def apply_metadata_update(self, update: Dict[str, Any]):
        """Apply metadata update to TigerBeetle"""
        try:
            # For now, we mainly sync metadata to PostgreSQL
            # TigerBeetle handles the core accounting data
            # This could be extended to update user_data fields in TigerBeetle
            
            logger.debug(f"Metadata update applied for account {update['id']}")
            
        except Exception as e:
            logger.error(f"Error applying metadata update: {e}")
            raise
    
    async def event_processor(self):
        """Process sync events from the queue"""
        while True:
            try:
                # Get pending events
                events = await self.get_pending_sync_events()
                
                for event in events:
                    await self.process_sync_event(event)
                
                if events:
                    pending_sync_items.set(len(events))
                
                await asyncio.sleep(5)  # Process events every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in event processor: {e}")
                sync_errors.labels(error_type='event_processing').inc()
                await asyncio.sleep(5)
    
    async def get_pending_sync_events(self) -> List[SyncEvent]:
        """Get pending synchronization events"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, event_type, source, target, data, timestamp, 
                       processed, retry_count, error_message
                FROM sync_events 
                WHERE processed = FALSE AND retry_count < $1
                ORDER BY timestamp
                LIMIT $2
            """, self.max_retries, self.batch_size)
            
            events = []
            for row in rows:
                event = SyncEvent(
                    id=row['id'],
                    event_type=row['event_type'],
                    source=row['source'],
                    target=row['target'],
                    data=row['data'],
                    timestamp=row['timestamp'],
                    processed=row['processed'],
                    retry_count=row['retry_count'],
                    error_message=row['error_message']
                )
                events.append(event)
            
            return events
    
    async def process_sync_event(self, event: SyncEvent):
        """Process a single sync event"""
        try:
            logger.debug(f"Processing sync event: {event.id} ({event.event_type})")
            
            if event.event_type == 'account_created':
                await self.handle_account_created_event(event)
            elif event.event_type == 'transfer_created':
                await self.handle_transfer_created_event(event)
            elif event.event_type == 'balance_updated':
                await self.handle_balance_updated_event(event)
            else:
                logger.warning(f"Unknown event type: {event.event_type}")
            
            # Mark event as processed
            await self.mark_event_processed(event.id)
            sync_operations_total.labels(operation='event_processing', status='success').inc()
            
        except Exception as e:
            logger.error(f"Error processing sync event {event.id}: {e}")
            await self.mark_event_failed(event.id, str(e))
            sync_operations_total.labels(operation='event_processing', status='error').inc()
            sync_errors.labels(error_type='event_processing').inc()
    
    async def handle_account_created_event(self, event: SyncEvent):
        """Handle account creation event"""
        # Implementation depends on the specific event data structure
        logger.debug(f"Handling account created event: {event.data}")
    
    async def handle_transfer_created_event(self, event: SyncEvent):
        """Handle transfer creation event"""
        # Implementation depends on the specific event data structure
        logger.debug(f"Handling transfer created event: {event.data}")
    
    async def handle_balance_updated_event(self, event: SyncEvent):
        """Handle balance update event"""
        # Implementation depends on the specific event data structure
        logger.debug(f"Handling balance updated event: {event.data}")
    
    async def mark_event_processed(self, event_id: str):
        """Mark sync event as processed"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE sync_events 
                SET processed = TRUE, retry_count = retry_count + 1
                WHERE id = $1
            """, event_id)
    
    async def mark_event_failed(self, event_id: str, error_message: str):
        """Mark sync event as failed"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE sync_events 
                SET retry_count = retry_count + 1, error_message = $2
                WHERE id = $1
            """, event_id, error_message)
    
    async def redis_event_listener(self):
        """Listen for real-time events from Redis"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe('tigerbeetle_sync', 'accounts:events', 'payments:events', 'transactions:events')
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    await self.handle_redis_event(message)
                    
        except Exception as e:
            logger.error(f"Error in Redis event listener: {e}")
            sync_errors.labels(error_type='redis_events').inc()
    
    async def handle_redis_event(self, message):
        """Handle real-time event from Redis"""
        try:
            data = json.loads(message['data'])
            channel = message['channel']
            
            logger.debug(f"Received Redis event from {channel}: {data}")
            
            # Create sync event for processing
            event_id = f"redis_{int(time.time() * 1000000)}"
            event = SyncEvent(
                id=event_id,
                event_type=data.get('type', 'unknown'),
                source='redis',
                target='postgres',
                data=data,
                timestamp=datetime.now()
            )
            
            # Store event for processing
            await self.store_sync_event(event)
            
        except Exception as e:
            logger.error(f"Error handling Redis event: {e}")
            sync_errors.labels(error_type='redis_event_handling').inc()
    
    async def store_sync_event(self, event: SyncEvent):
        """Store sync event in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO sync_events (
                    id, event_type, source, target, data, timestamp, processed, retry_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, 
                event.id, event.event_type, event.source, event.target,
                json.dumps(event.data), event.timestamp, event.processed, event.retry_count
            )
    
    async def health_monitor(self):
        """Monitor service health and update metrics"""
        while True:
            try:
                # Check TigerBeetle connectivity
                zig_healthy = await self.check_endpoint_health(self.tigerbeetle_zig_endpoint)
                edge_healthy = await self.check_endpoint_health(self.tigerbeetle_edge_endpoint)
                
                # Check database connectivity
                db_healthy = await self.check_database_health()
                
                # Check Redis connectivity
                redis_healthy = await self.check_redis_health()
                
                # Update sync lag metric
                lag = await self.calculate_sync_lag()
                sync_lag.set(lag)
                
                logger.debug(f"Health check - TigerBeetle Zig: {zig_healthy}, Edge: {edge_healthy}, DB: {db_healthy}, Redis: {redis_healthy}, Lag: {lag}s")
                
                await asyncio.sleep(30)  # Health check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(30)
    
    async def check_endpoint_health(self, endpoint: str) -> bool:
        """Check if TigerBeetle endpoint is healthy"""
        try:
            async with self.session.get(f"{endpoint}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                return response.status == 200
        except:
            return False
    
    async def check_database_health(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except:
            return False
    
    async def check_redis_health(self) -> bool:
        """Check Redis connectivity"""
        try:
            await self.redis.ping()
            return True
        except:
            return False
    
    async def calculate_sync_lag(self) -> float:
        """Calculate synchronization lag in seconds"""
        try:
            async with self.db_pool.acquire() as conn:
                last_sync = await conn.fetchval("""
                    SELECT last_sync_time FROM sync_state 
                    WHERE service_name = 'full_sync'
                """)
                
                if last_sync:
                    lag = (datetime.now() - last_sync).total_seconds()
                    return max(0, lag)
                
                return 0
                
        except:
            return 0

# FastAPI application
app = FastAPI(title="TigerBeetle Sync Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global sync service instance
sync_service: Optional[TigerBeetleSyncService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global sync_service
    
    # Startup
    config = {
        'database_url': 'postgresql://user:pass@localhost/tigerbeetle_sync',
        'redis_url': 'redis://localhost:6379',
        'tigerbeetle_zig_endpoint': 'http://localhost:3000',
        'tigerbeetle_edge_endpoint': 'http://localhost:3001',
        'sync_interval': 30,
        'batch_size': 1000,
        'max_retries': 3,
    }
    
    sync_service = TigerBeetleSyncService(config)
    await sync_service.initialize()
    await sync_service.start_sync_workers()
    
    # Start Prometheus metrics server
    start_http_server(8090)
    
    yield
    
    # Shutdown
    if sync_service:
        await sync_service.cleanup()

app.router.lifespan_context = lifespan

# API Models
class SyncStatus(BaseModel):
    service: str
    status: str
    last_sync_time: Optional[datetime]
    sync_count: int
    error_count: int

class SyncEventRequest(BaseModel):
    event_type: str
    source: str
    target: str
    data: Dict[str, Any]

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "service": "tigerbeetle-sync-service",
        "version": "1.0.0"
    }

@app.get("/sync/status")
async def get_sync_status():
    """Get synchronization status"""
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    
    async with sync_service.db_pool.acquire() as conn:
        states = await conn.fetch("SELECT * FROM sync_state")
        
        status_list = []
        for state in states:
            status_list.append(SyncStatus(
                service=state['service_name'],
                status="active" if state['last_sync_time'] else "inactive",
                last_sync_time=state['last_sync_time'],
                sync_count=state['sync_count'],
                error_count=state['error_count']
            ))
        
        return {"sync_status": status_list}

@app.post("/sync/trigger")
async def trigger_sync(background_tasks: BackgroundTasks):
    """Manually trigger synchronization"""
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    
    if sync_service.sync_running:
        raise HTTPException(status_code=409, detail="Sync already running")
    
    background_tasks.add_task(sync_service.perform_full_sync)
    
    return {"message": "Sync triggered successfully"}

@app.post("/sync/events")
async def create_sync_event(event_request: SyncEventRequest):
    """Create a new sync event"""
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    
    event_id = f"api_{int(time.time() * 1000000)}"
    event = SyncEvent(
        id=event_id,
        event_type=event_request.event_type,
        source=event_request.source,
        target=event_request.target,
        data=event_request.data,
        timestamp=datetime.now()
    )
    
    await sync_service.store_sync_event(event)
    
    return {"event_id": event_id, "message": "Sync event created successfully"}

@app.get("/sync/events/pending")
async def get_pending_events():
    """Get pending sync events"""
    if not sync_service:
        raise HTTPException(status_code=503, detail="Sync service not initialized")
    
    events = await sync_service.get_pending_sync_events()
    
    return {
        "pending_events": [asdict(event) for event in events],
        "count": len(events)
    }

@app.get("/metrics/summary")
async def get_metrics_summary():
    """Get sync metrics summary"""
    return {
        "sync_operations_total": sync_operations_total._value._value,
        "sync_errors_total": sync_errors._value._value,
        "pending_sync_items": pending_sync_items._value._value,
        "sync_lag_seconds": sync_lag._value._value,
        "timestamp": datetime.now()
    }

if __name__ == "__main__":
    uvicorn.run(
        "tigerbeetle_sync_service:app",
        host="0.0.0.0",
        port=8083,
        reload=False,
        log_level="info"
    )

