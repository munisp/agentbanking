import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
#!/usr/bin/env python3
"""
TigerBeetle Sync Manager
Orchestrates bidirectional synchronization between Zig primary and Go edge instances
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uuid

import asyncpg
import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("tigerbeetle-sync-manager")
app.include_router(metrics_router)

from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data Models
class SyncNode(BaseModel):
    id: str
    type: str  # "zig-primary", "go-edge"
    url: str
    status: str  # "online", "offline", "syncing"
    last_sync: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    pending_events: int = 0
    sync_errors: List[str] = []

class SyncEvent(BaseModel):
    id: str
    type: str  # "account", "transfer"
    operation: str  # "create", "update"
    data: Dict[str, Any]
    source_node: str
    target_nodes: List[str]
    timestamp: int
    processed_nodes: List[str] = []
    failed_nodes: List[str] = []
    retry_count: int = 0
    max_retries: int = 3

class SyncMetrics(BaseModel):
    total_events: int
    processed_events: int
    failed_events: int
    pending_events: int
    sync_rate: float  # events per second
    error_rate: float  # percentage
    average_sync_time: float  # seconds
    nodes_online: int
    nodes_offline: int

class TigerBeetleSyncManager:
    def __init__(self):
        self.app = FastAPI(
            title="TigerBeetle Sync Manager",
            description="Orchestrates bidirectional synchronization between TigerBeetle instances",
            version="1.0.0"
        )
        
        # Configuration
        self.database_url = os.getenv("DATABASE_URL", "postgresql://banking_user:secure_banking_password@localhost:5432/remittance")
        self.redis_url = os.getenv("REDIS_URL", "redis://:redis_secure_password@localhost:6379")
        self.sync_interval = int(os.getenv("SYNC_INTERVAL", "5"))  # seconds
        self.heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # seconds
        self.max_retry_attempts = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
        
        # State
        self.db_pool = None
        self.redis_client = None
        self.sync_nodes: Dict[str, SyncNode] = {}
        self.sync_events: Dict[str, SyncEvent] = {}
        self.sync_metrics = SyncMetrics(
            total_events=0,
            processed_events=0,
            failed_events=0,
            pending_events=0,
            sync_rate=0.0,
            error_rate=0.0,
            average_sync_time=0.0,
            nodes_online=0,
            nodes_offline=0
        )
        
        # HTTP client for node communication
        self.http_client = None
        
        # Setup FastAPI
        self.setup_fastapi()
    
    def setup_fastapi(self):
        """Setup FastAPI application"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Event handlers
        self.app.add_event_handler("startup", self.startup)
        self.app.add_event_handler("shutdown", self.shutdown)
        
        # Setup routes
        self.setup_routes()
    
    def setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "service": "tigerbeetle-sync-manager",
                "timestamp": datetime.utcnow().isoformat(),
                "nodes_registered": len(self.sync_nodes),
                "nodes_online": self.sync_metrics.nodes_online,
                "pending_events": self.sync_metrics.pending_events
            }
        
        @self.app.post("/nodes/register")
        async def register_node(node: SyncNode):
            """Register a TigerBeetle node for synchronization"""
            try:
                # Validate node connectivity
                if not await self.validate_node_connectivity(node):
                    raise HTTPException(status_code=400, detail="Node is not accessible")
                
                # Register node
                node.status = "online"
                node.last_heartbeat = datetime.utcnow()
                self.sync_nodes[node.id] = node
                
                # Store in database
                await self.store_node_registration(node)
                
                logger.info(f"Registered node: {node.id} ({node.type})")
                
                return {
                    "success": True,
                    "message": f"Node {node.id} registered successfully",
                    "node_id": node.id
                }
                
            except Exception as e:
                logger.error(f"Error registering node: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/nodes/{node_id}")
        async def unregister_node(node_id: str):
            """Unregister a TigerBeetle node"""
            try:
                if node_id not in self.sync_nodes:
                    raise HTTPException(status_code=404, detail="Node not found")
                
                # Remove node
                del self.sync_nodes[node_id]
                
                # Remove from database
                await self.remove_node_registration(node_id)
                
                logger.info(f"Unregistered node: {node_id}")
                
                return {
                    "success": True,
                    "message": f"Node {node_id} unregistered successfully"
                }
                
            except Exception as e:
                logger.error(f"Error unregistering node: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/nodes")
        async def get_nodes():
            """Get all registered nodes"""
            return {
                "nodes": list(self.sync_nodes.values()),
                "total_nodes": len(self.sync_nodes),
                "online_nodes": len([n for n in self.sync_nodes.values() if n.status == "online"]),
                "offline_nodes": len([n for n in self.sync_nodes.values() if n.status == "offline"])
            }
        
        @self.app.get("/nodes/{node_id}")
        async def get_node(node_id: str):
            """Get specific node details"""
            if node_id not in self.sync_nodes:
                raise HTTPException(status_code=404, detail="Node not found")
            
            return self.sync_nodes[node_id]
        
        @self.app.post("/sync/trigger")
        async def trigger_sync():
            """Manually trigger synchronization"""
            try:
                await self.perform_sync_cycle()
                return {
                    "success": True,
                    "message": "Sync cycle triggered successfully"
                }
            except Exception as e:
                logger.error(f"Error triggering sync: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/sync/status")
        async def get_sync_status():
            """Get synchronization status"""
            return {
                "sync_active": any(n.status == "syncing" for n in self.sync_nodes.values()),
                "last_sync_cycle": max([n.last_sync for n in self.sync_nodes.values() if n.last_sync], default=None),
                "pending_events": self.sync_metrics.pending_events,
                "sync_metrics": self.sync_metrics
            }
        
        @self.app.get("/sync/events")
        async def get_sync_events(limit: int = 100, status: str = None):
            """Get sync events"""
            try:
                events = await self.get_sync_events_from_db(limit, status)
                return {
                    "events": events,
                    "count": len(events)
                }
            except Exception as e:
                logger.error(f"Error getting sync events: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/sync/events/{event_id}/retry")
        async def retry_sync_event(event_id: str):
            """Retry a failed sync event"""
            try:
                if event_id not in self.sync_events:
                    raise HTTPException(status_code=404, detail="Sync event not found")
                
                event = self.sync_events[event_id]
                if event.retry_count >= event.max_retries:
                    raise HTTPException(status_code=400, detail="Maximum retry attempts reached")
                
                # Reset failed nodes and retry
                event.failed_nodes = []
                event.retry_count += 1
                
                await self.process_sync_event(event)
                
                return {
                    "success": True,
                    "message": f"Sync event {event_id} retry initiated"
                }
                
            except Exception as e:
                logger.error(f"Error retrying sync event: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/metrics")
        async def get_metrics():
            """Get sync manager metrics"""
            # Update metrics
            await self.update_metrics()
            
            return {
                "sync_metrics": self.sync_metrics,
                "node_metrics": {
                    node_id: {
                        "status": node.status,
                        "last_sync": node.last_sync,
                        "last_heartbeat": node.last_heartbeat,
                        "pending_events": node.pending_events,
                        "error_count": len(node.sync_errors)
                    }
                    for node_id, node in self.sync_nodes.items()
                },
                "system_metrics": {
                    "uptime_seconds": time.time() - getattr(self, 'start_time', time.time()),
                    "memory_usage": await self.get_memory_usage(),
                    "database_connections": await self.get_db_connection_count()
                }
            }
    
    async def startup(self):
        """Startup event handler"""
        logger.info("Starting TigerBeetle Sync Manager...")
        self.start_time = time.time()
        
        # Initialize database connection
        await self.init_database()
        
        # Initialize Redis connection
        await self.init_redis()
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Load registered nodes from database
        await self.load_registered_nodes()
        
        # Start background tasks
        asyncio.create_task(self.sync_worker())
        asyncio.create_task(self.heartbeat_worker())
        asyncio.create_task(self.metrics_worker())
        
        logger.info("TigerBeetle Sync Manager started successfully")
    
    async def shutdown(self):
        """Shutdown event handler"""
        logger.info("Shutting down TigerBeetle Sync Manager...")
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
        
        # Close database connection
        if self.db_pool:
            await self.db_pool.close()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("TigerBeetle Sync Manager shut down")
    
    async def init_database(self):
        """Initialize PostgreSQL connection"""
        try:
            self.db_pool = await asyncpg.create_pool(self.database_url)
            
            # Create tables
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tigerbeetle_sync_nodes (
                        id VARCHAR(100) PRIMARY KEY,
                        type VARCHAR(50) NOT NULL,
                        url VARCHAR(200) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        last_sync TIMESTAMP,
                        last_heartbeat TIMESTAMP,
                        pending_events INTEGER DEFAULT 0,
                        sync_errors JSONB DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tigerbeetle_sync_events_manager (
                        id VARCHAR(100) PRIMARY KEY,
                        type VARCHAR(20) NOT NULL,
                        operation VARCHAR(20) NOT NULL,
                        data JSONB NOT NULL,
                        source_node VARCHAR(100) NOT NULL,
                        target_nodes JSONB NOT NULL,
                        timestamp BIGINT NOT NULL,
                        processed_nodes JSONB DEFAULT '[]',
                        failed_nodes JSONB DEFAULT '[]',
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sync_events_status 
                    ON tigerbeetle_sync_events_manager(status, timestamp)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sync_events_source 
                    ON tigerbeetle_sync_events_manager(source_node)
                """)
            
            logger.info("Database connection initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Redis connection initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
            raise
    
    async def load_registered_nodes(self):
        """Load registered nodes from database"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM tigerbeetle_sync_nodes")
                
                for row in rows:
                    node = SyncNode(
                        id=row["id"],
                        type=row["type"],
                        url=row["url"],
                        status=row["status"],
                        last_sync=row["last_sync"],
                        last_heartbeat=row["last_heartbeat"],
                        pending_events=row["pending_events"],
                        sync_errors=json.loads(row["sync_errors"]) if row["sync_errors"] else []
                    )
                    self.sync_nodes[node.id] = node
                
                logger.info(f"Loaded {len(self.sync_nodes)} registered nodes")
                
        except Exception as e:
            logger.error(f"Failed to load registered nodes: {str(e)}")
    
    async def validate_node_connectivity(self, node: SyncNode) -> bool:
        """Validate that a node is accessible"""
        try:
            response = await self.http_client.get(f"{node.url}/health", timeout=10.0)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Node connectivity validation failed for {node.id}: {str(e)}")
            return False
    
    async def store_node_registration(self, node: SyncNode):
        """Store node registration in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tigerbeetle_sync_nodes 
                (id, type, url, status, last_heartbeat, sync_errors)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    type = EXCLUDED.type,
                    url = EXCLUDED.url,
                    status = EXCLUDED.status,
                    last_heartbeat = EXCLUDED.last_heartbeat,
                    updated_at = CURRENT_TIMESTAMP
            """, node.id, node.type, node.url, node.status, 
            node.last_heartbeat, json.dumps(node.sync_errors))
    
    async def remove_node_registration(self, node_id: str):
        """Remove node registration from database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM tigerbeetle_sync_nodes WHERE id = $1", node_id)
    
    async def sync_worker(self):
        """Background sync worker"""
        while True:
            try:
                await self.perform_sync_cycle()
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Sync worker error: {str(e)}")
                await asyncio.sleep(self.sync_interval * 2)  # Wait longer on error
    
    async def heartbeat_worker(self):
        """Background heartbeat worker"""
        while True:
            try:
                await self.check_node_heartbeats()
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Heartbeat worker error: {str(e)}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def metrics_worker(self):
        """Background metrics worker"""
        while True:
            try:
                await self.update_metrics()
                await asyncio.sleep(60)  # Update metrics every minute
                
            except Exception as e:
                logger.error(f"Metrics worker error: {str(e)}")
                await asyncio.sleep(60)
    
    async def perform_sync_cycle(self):
        """Perform one complete sync cycle"""
        logger.info("Starting sync cycle...")
        
        # Get all online nodes
        online_nodes = [node for node in self.sync_nodes.values() if node.status == "online"]
        
        if len(online_nodes) < 2:
            logger.warning("Not enough online nodes for synchronization")
            return
        
        # Collect sync events from all nodes
        all_events = []
        
        for node in online_nodes:
            try:
                node.status = "syncing"
                events = await self.collect_sync_events_from_node(node)
                all_events.extend(events)
                
            except Exception as e:
                logger.error(f"Failed to collect events from node {node.id}: {str(e)}")
                node.sync_errors.append(f"Collection failed: {str(e)}")
                node.status = "offline"
                continue
        
        # Process and distribute sync events
        for event in all_events:
            await self.process_sync_event(event)
        
        # Update node statuses
        for node in online_nodes:
            if node.status == "syncing":
                node.status = "online"
                node.last_sync = datetime.utcnow()
        
        logger.info(f"Sync cycle completed - processed {len(all_events)} events")
    
    async def collect_sync_events_from_node(self, node: SyncNode) -> List[SyncEvent]:
        """Collect sync events from a specific node"""
        try:
            response = await self.http_client.get(f"{node.url}/sync/events?limit=100")
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            for event_data in data.get("events", []):
                # Determine target nodes (all other nodes except source)
                target_nodes = [n.id for n in self.sync_nodes.values() if n.id != node.id and n.status == "online"]
                
                event = SyncEvent(
                    id=event_data["id"],
                    type=event_data["type"],
                    operation=event_data["operation"],
                    data=event_data["data"],
                    source_node=node.id,
                    target_nodes=target_nodes,
                    timestamp=event_data["timestamp"]
                )
                
                events.append(event)
                self.sync_events[event.id] = event
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to collect sync events from {node.id}: {str(e)}")
            raise
    
    async def process_sync_event(self, event: SyncEvent):
        """Process a sync event by distributing it to target nodes"""
        try:
            # Store event in database
            await self.store_sync_event(event)
            
            # Distribute to target nodes
            for target_node_id in event.target_nodes:
                if target_node_id in event.processed_nodes or target_node_id in event.failed_nodes:
                    continue  # Skip already processed or failed nodes
                
                target_node = self.sync_nodes.get(target_node_id)
                if not target_node or target_node.status != "online":
                    continue
                
                try:
                    await self.send_sync_event_to_node(event, target_node)
                    event.processed_nodes.append(target_node_id)
                    
                except Exception as e:
                    logger.error(f"Failed to send sync event to {target_node_id}: {str(e)}")
                    event.failed_nodes.append(target_node_id)
                    target_node.sync_errors.append(f"Sync failed: {str(e)}")
            
            # Update event status
            if len(event.failed_nodes) == 0:
                event_status = "completed"
            elif len(event.processed_nodes) > 0:
                event_status = "partial"
            else:
                event_status = "failed"
            
            # Update event in database
            await self.update_sync_event_status(event, event_status)
            
            # Mark event as processed on source node
            if event.source_node in self.sync_nodes:
                await self.mark_event_processed_on_source(event)
            
        except Exception as e:
            logger.error(f"Failed to process sync event {event.id}: {str(e)}")
    
    async def send_sync_event_to_node(self, event: SyncEvent, target_node: SyncNode):
        """Send sync event to a target node"""
        try:
            # Prepare event data for target node
            event_data = {
                "events": [{
                    "id": event.id,
                    "type": event.type,
                    "operation": event.operation,
                    "data": event.data,
                    "source": event.source_node,
                    "timestamp": event.timestamp
                }]
            }
            
            # Send to target node
            response = await self.http_client.post(
                f"{target_node.url}/sync/from-edge",
                json=event_data,
                timeout=30.0
            )
            response.raise_for_status()
            
            logger.debug(f"Sent sync event {event.id} to {target_node.id}")
            
        except Exception as e:
            logger.error(f"Failed to send sync event to {target_node.id}: {str(e)}")
            raise
    
    async def store_sync_event(self, event: SyncEvent):
        """Store sync event in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tigerbeetle_sync_events_manager 
                (id, type, operation, data, source_node, target_nodes, timestamp, 
                 processed_nodes, failed_nodes, retry_count, max_retries, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (id) DO UPDATE SET
                    processed_nodes = EXCLUDED.processed_nodes,
                    failed_nodes = EXCLUDED.failed_nodes,
                    retry_count = EXCLUDED.retry_count,
                    status = EXCLUDED.status,
                    updated_at = CURRENT_TIMESTAMP
            """, event.id, event.type, event.operation, json.dumps(event.data),
            event.source_node, json.dumps(event.target_nodes), event.timestamp,
            json.dumps(event.processed_nodes), json.dumps(event.failed_nodes),
            event.retry_count, event.max_retries, "pending")
    
    async def update_sync_event_status(self, event: SyncEvent, status: str):
        """Update sync event status in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE tigerbeetle_sync_events_manager 
                SET status = $1, processed_nodes = $2, failed_nodes = $3, 
                    retry_count = $4, updated_at = CURRENT_TIMESTAMP
                WHERE id = $5
            """, status, json.dumps(event.processed_nodes), json.dumps(event.failed_nodes),
            event.retry_count, event.id)
    
    async def mark_event_processed_on_source(self, event: SyncEvent):
        """Mark event as processed on source node"""
        try:
            source_node = self.sync_nodes.get(event.source_node)
            if not source_node:
                return
            
            response = await self.http_client.post(
                f"{source_node.url}/sync/events/mark-processed",
                json=[event.id],
                timeout=10.0
            )
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Failed to mark event processed on source {event.source_node}: {str(e)}")
    
    async def check_node_heartbeats(self):
        """Check heartbeats of all registered nodes"""
        for node_id, node in self.sync_nodes.items():
            try:
                response = await self.http_client.get(f"{node.url}/health", timeout=10.0)
                
                if response.status_code == 200:
                    node.status = "online"
                    node.last_heartbeat = datetime.utcnow()
                else:
                    node.status = "offline"
                    
            except Exception as e:
                logger.warning(f"Heartbeat failed for node {node_id}: {str(e)}")
                node.status = "offline"
                
                # Mark as offline if no heartbeat for 5 minutes
                if node.last_heartbeat and (datetime.utcnow() - node.last_heartbeat).total_seconds() > 300:
                    node.status = "offline"
            
            # Update node status in database
            await self.update_node_status(node)
    
    async def update_node_status(self, node: SyncNode):
        """Update node status in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE tigerbeetle_sync_nodes 
                SET status = $1, last_heartbeat = $2, last_sync = $3, 
                    pending_events = $4, sync_errors = $5, updated_at = CURRENT_TIMESTAMP
                WHERE id = $6
            """, node.status, node.last_heartbeat, node.last_sync,
            node.pending_events, json.dumps(node.sync_errors), node.id)
    
    async def update_metrics(self):
        """Update sync metrics"""
        try:
            async with self.db_pool.acquire() as conn:
                # Get event counts
                total_events = await conn.fetchval("SELECT COUNT(*) FROM tigerbeetle_sync_events_manager")
                processed_events = await conn.fetchval("SELECT COUNT(*) FROM tigerbeetle_sync_events_manager WHERE status = 'completed'")
                failed_events = await conn.fetchval("SELECT COUNT(*) FROM tigerbeetle_sync_events_manager WHERE status = 'failed'")
                pending_events = await conn.fetchval("SELECT COUNT(*) FROM tigerbeetle_sync_events_manager WHERE status = 'pending'")
                
                # Calculate rates
                error_rate = (failed_events / total_events * 100) if total_events > 0 else 0.0
                
                # Count online/offline nodes
                nodes_online = len([n for n in self.sync_nodes.values() if n.status == "online"])
                nodes_offline = len([n for n in self.sync_nodes.values() if n.status == "offline"])
                
                # Update metrics
                self.sync_metrics.total_events = total_events or 0
                self.sync_metrics.processed_events = processed_events or 0
                self.sync_metrics.failed_events = failed_events or 0
                self.sync_metrics.pending_events = pending_events or 0
                self.sync_metrics.error_rate = error_rate
                self.sync_metrics.nodes_online = nodes_online
                self.sync_metrics.nodes_offline = nodes_offline
                
        except Exception as e:
            logger.error(f"Failed to update metrics: {str(e)}")
    
    async def get_sync_events_from_db(self, limit: int = 100, status: str = None) -> List[Dict]:
        """Get sync events from database"""
        async with self.db_pool.acquire() as conn:
            if status:
                rows = await conn.fetch("""
                    SELECT * FROM tigerbeetle_sync_events_manager 
                    WHERE status = $1 
                    ORDER BY timestamp DESC 
                    LIMIT $2
                """, status, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM tigerbeetle_sync_events_manager 
                    ORDER BY timestamp DESC 
                    LIMIT $1
                """, limit)
            
            events = []
            for row in rows:
                events.append({
                    "id": row["id"],
                    "type": row["type"],
                    "operation": row["operation"],
                    "data": json.loads(row["data"]),
                    "source_node": row["source_node"],
                    "target_nodes": json.loads(row["target_nodes"]),
                    "timestamp": row["timestamp"],
                    "processed_nodes": json.loads(row["processed_nodes"]),
                    "failed_nodes": json.loads(row["failed_nodes"]),
                    "retry_count": row["retry_count"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat()
                })
            
            return events
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent()
            }
        except ImportError:
            return {"error": "psutil not available"}
    
    async def get_db_connection_count(self) -> int:
        """Get database connection count"""
        try:
            return len(self.db_pool._holders) if self.db_pool else 0
        except:
            return 0

# Create service instance
service = TigerBeetleSyncManager()
app = service.app

if __name__ == "__main__":
    uvicorn.run(
        "tigerbeetle_sync_manager:app",
        host="0.0.0.0",
        port=8032,
        reload=False,
        log_level="info"
    )
