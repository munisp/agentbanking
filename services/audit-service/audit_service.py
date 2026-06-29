import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Audit Service for Remittance Platform
Tracks all system activities, changes, and compliance events
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("audit-service")
app.include_router(metrics_router)

from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager

import os
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuditEvent(BaseModel):
    event_type: str
    user_id: str
    resource_type: str
    resource_id: str
    action: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditService:
    """Comprehensive audit service"""
    
    def __init__(self):
        self.db_pool = None
        self.redis_client = None
        
    async def initialize(self):
        """Initialize audit service"""
        try:
            # Initialize database connection
            self.db_pool = await asyncpg.create_pool(
                host="postgres",
                port=5432,
                user="remittance_user", 
                password=os.getenv('DB_PASSWORD', ''),
                database="remittance_db",
                min_size=5,
                max_size=20
            )
            
            # Initialize Redis connection
            self.redis_client = redis.Redis(
                host="redis",
                port=6379,
                decode_responses=True
            )
            
            # Create audit tables
            await self._create_audit_tables()
            
            logger.info("Audit Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Audit Service: {str(e)}")
            raise
    
    async def _create_audit_tables(self):
        """Create audit-related database tables"""
        create_tables_sql = """
        -- Audit events table
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(100) NOT NULL,
            user_id VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100) NOT NULL,
            resource_id VARCHAR(100) NOT NULL,
            action VARCHAR(100) NOT NULL,
            old_values JSONB,
            new_values JSONB,
            metadata JSONB DEFAULT '{}',
            ip_address INET,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Audit trail table for compliance
        CREATE TABLE IF NOT EXISTS audit_trail (
            trail_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id VARCHAR(100),
            user_id VARCHAR(100) NOT NULL,
            action_sequence INTEGER,
            action_description TEXT NOT NULL,
            risk_level VARCHAR(20) DEFAULT 'low',
            compliance_flags TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_events_resource ON audit_events(resource_type, resource_id);
        CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_trail_user ON audit_trail(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_trail_session ON audit_trail(session_id);
        """
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(create_tables_sql)
    
    async def log_event(self, event: AuditEvent) -> str:
        """Log audit event"""
        try:
            query = """
            INSERT INTO audit_events (
                event_type, user_id, resource_type, resource_id, action,
                old_values, new_values, metadata, ip_address, user_agent
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING event_id
            """
            
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    event.event_type,
                    event.user_id,
                    event.resource_type,
                    event.resource_id,
                    event.action,
                    json.dumps(event.old_values) if event.old_values else None,
                    json.dumps(event.new_values) if event.new_values else None,
                    json.dumps(event.metadata),
                    event.ip_address,
                    event.user_agent
                )
                
                event_id = str(row['event_id'])
                
                # Cache recent events in Redis
                await self.redis_client.lpush(
                    f"audit:user:{event.user_id}",
                    json.dumps({
                        "event_id": event_id,
                        "action": event.action,
                        "resource": f"{event.resource_type}:{event.resource_id}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                )
                
                # Keep only last 100 events per user
                await self.redis_client.ltrim(f"audit:user:{event.user_id}", 0, 99)
                
                return event_id
                
        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to log audit event")

# FastAPI Application
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await audit_service.initialize()
    yield
    # Shutdown
    if audit_service.db_pool:
        await audit_service.db_pool.close()
    if audit_service.redis_client:
        await audit_service.redis_client.close()

app = FastAPI(
    title="Audit Service",
    description="Comprehensive audit service for Remittance Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
audit_service = AuditService()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "audit-service",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/v1/audit/events")
async def log_audit_event(event: AuditEvent):
    """Log audit event"""
    event_id = await audit_service.log_event(event)
    return {"event_id": event_id, "status": "logged"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8023)
