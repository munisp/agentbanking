"""
Transaction Idempotency Service for Cash In/Cash Out Workflows

Provides exactly-once semantics for financial transactions:
- Redis-based fast path for idempotency checks
- PostgreSQL persistence for audit trail
- Request hash validation to detect mismatched requests
- Automatic expiry and cleanup
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

import asyncpg
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class TransactionIdempotencyStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class IdempotencyRecord:
    key: str
    status: TransactionIdempotencyStatus
    request_hash: str
    transaction_id: Optional[str] = None
    workflow_id: Optional[str] = None
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class TransactionIdempotencyService:
    """
    Idempotency service for financial transactions
    
    Features:
    - Exactly-once transaction execution
    - Request hash validation
    - Automatic expiry (default 24 hours)
    - Redis fast path + PostgreSQL persistence
    """
    
    DEFAULT_TTL_HOURS = 24
    REDIS_PREFIX = "txn:idempotency:"
    
    def __init__(
        self,
        redis_client: redis.Redis,
        db_pool: asyncpg.Pool,
        ttl_hours: int = DEFAULT_TTL_HOURS
    ):
        self.redis = redis_client
        self.db_pool = db_pool
        self.ttl = timedelta(hours=ttl_hours)
    
    async def initialize(self):
        """Initialize database tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transaction_idempotency (
                    key VARCHAR(255) PRIMARY KEY,
                    status VARCHAR(50) NOT NULL,
                    request_hash VARCHAR(64) NOT NULL,
                    transaction_id VARCHAR(255),
                    workflow_id VARCHAR(255),
                    response JSONB,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_txn_idempotency_status 
                ON transaction_idempotency(status);
                
                CREATE INDEX IF NOT EXISTS idx_txn_idempotency_expires 
                ON transaction_idempotency(expires_at);
                
                CREATE INDEX IF NOT EXISTS idx_txn_idempotency_transaction 
                ON transaction_idempotency(transaction_id);
            """)
        logger.info("Transaction idempotency tables initialized")
    
    def _compute_request_hash(self, request_data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of request data"""
        sorted_json = json.dumps(request_data, sort_keys=True, default=str)
        return hashlib.sha256(sorted_json.encode()).hexdigest()
    
    def _redis_key(self, key: str) -> str:
        """Generate Redis key"""
        return f"{self.REDIS_PREFIX}{key}"
    
    async def check(
        self,
        idempotency_key: str,
        request_data: Dict[str, Any]
    ) -> Optional[IdempotencyRecord]:
        """
        Check if transaction with this idempotency key exists
        
        Returns:
        - None if no record exists (safe to proceed)
        - IdempotencyRecord if exists (check status and request_hash)
        """
        request_hash = self._compute_request_hash(request_data)
        
        # Fast path: check Redis
        redis_key = self._redis_key(idempotency_key)
        cached = await self.redis.hgetall(redis_key)
        
        if cached:
            # Validate request hash
            stored_hash = cached.get("request_hash", "")
            if stored_hash and stored_hash != request_hash:
                raise IdempotencyConflictError(
                    f"Request hash mismatch for key {idempotency_key}. "
                    "Different request data for same idempotency key."
                )
            
            return IdempotencyRecord(
                key=idempotency_key,
                status=TransactionIdempotencyStatus(cached.get("status", "pending")),
                request_hash=stored_hash,
                transaction_id=cached.get("transaction_id"),
                workflow_id=cached.get("workflow_id"),
                response=json.loads(cached["response"]) if cached.get("response") else None,
                error=cached.get("error")
            )
        
        # Slow path: check PostgreSQL
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM transaction_idempotency WHERE key = $1",
                idempotency_key
            )
            
            if row:
                stored_hash = row["request_hash"]
                if stored_hash != request_hash:
                    raise IdempotencyConflictError(
                        f"Request hash mismatch for key {idempotency_key}"
                    )
                
                # Repopulate Redis cache
                await self._cache_to_redis(idempotency_key, dict(row))
                
                return IdempotencyRecord(
                    key=idempotency_key,
                    status=TransactionIdempotencyStatus(row["status"]),
                    request_hash=stored_hash,
                    transaction_id=row["transaction_id"],
                    workflow_id=row["workflow_id"],
                    response=row["response"],
                    error=row["error"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    expires_at=row["expires_at"]
                )
        
        return None
    
    async def start(
        self,
        idempotency_key: str,
        request_data: Dict[str, Any],
        transaction_id: str,
        workflow_id: Optional[str] = None
    ) -> bool:
        """
        Start processing a transaction with idempotency protection
        
        Returns True if acquired, False if already processing
        """
        request_hash = self._compute_request_hash(request_data)
        expires_at = datetime.utcnow() + self.ttl
        
        # Try to acquire lock in Redis
        redis_key = self._redis_key(idempotency_key)
        acquired = await self.redis.hsetnx(redis_key, "status", "processing")
        
        if not acquired:
            # Check if it's our own stale lock
            existing_status = await self.redis.hget(redis_key, "status")
            if existing_status == "processing":
                return False
        
        # Set full record in Redis
        await self.redis.hset(redis_key, mapping={
            "status": "processing",
            "request_hash": request_hash,
            "transaction_id": transaction_id,
            "workflow_id": workflow_id or "",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })
        await self.redis.expireat(redis_key, expires_at)
        
        # Persist to PostgreSQL
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO transaction_idempotency 
                (key, status, request_hash, transaction_id, workflow_id, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (key) DO UPDATE SET
                    status = EXCLUDED.status,
                    transaction_id = EXCLUDED.transaction_id,
                    workflow_id = EXCLUDED.workflow_id,
                    updated_at = NOW()
            """, idempotency_key, "processing", request_hash, 
                transaction_id, workflow_id, expires_at)
        
        logger.info(f"Started idempotent transaction: {idempotency_key} -> {transaction_id}")
        return True
    
    async def complete(
        self,
        idempotency_key: str,
        response: Dict[str, Any]
    ):
        """Mark transaction as completed with response"""
        redis_key = self._redis_key(idempotency_key)
        
        await self.redis.hset(redis_key, mapping={
            "status": "completed",
            "response": json.dumps(response, default=str),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE transaction_idempotency 
                SET status = 'completed', response = $2, updated_at = NOW()
                WHERE key = $1
            """, idempotency_key, json.dumps(response, default=str))
        
        logger.info(f"Completed idempotent transaction: {idempotency_key}")
    
    async def fail(
        self,
        idempotency_key: str,
        error: str
    ):
        """Mark transaction as failed with error"""
        redis_key = self._redis_key(idempotency_key)
        
        await self.redis.hset(redis_key, mapping={
            "status": "failed",
            "error": error,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE transaction_idempotency 
                SET status = 'failed', error = $2, updated_at = NOW()
                WHERE key = $1
            """, idempotency_key, error)
        
        logger.info(f"Failed idempotent transaction: {idempotency_key} - {error}")
    
    async def mark_compensated(
        self,
        idempotency_key: str,
        compensation_details: Dict[str, Any]
    ):
        """Mark transaction as compensated (rolled back)"""
        redis_key = self._redis_key(idempotency_key)
        
        await self.redis.hset(redis_key, mapping={
            "status": "compensated",
            "response": json.dumps(compensation_details, default=str),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE transaction_idempotency 
                SET status = 'compensated', 
                    response = $2,
                    updated_at = NOW()
                WHERE key = $1
            """, idempotency_key, json.dumps(compensation_details, default=str))
        
        logger.info(f"Compensated transaction: {idempotency_key}")
    
    async def _cache_to_redis(self, key: str, data: Dict[str, Any]):
        """Cache record to Redis"""
        redis_key = self._redis_key(key)
        mapping = {
            "status": data.get("status", ""),
            "request_hash": data.get("request_hash", ""),
            "transaction_id": data.get("transaction_id", ""),
            "workflow_id": data.get("workflow_id", ""),
            "response": json.dumps(data.get("response")) if data.get("response") else "",
            "error": data.get("error", "")
        }
        await self.redis.hset(redis_key, mapping=mapping)
        
        if data.get("expires_at"):
            await self.redis.expireat(redis_key, data["expires_at"])
    
    async def cleanup_expired(self) -> int:
        """Clean up expired idempotency records"""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM transaction_idempotency 
                WHERE expires_at < NOW()
            """)
            count = int(result.split()[-1]) if result else 0
        
        logger.info(f"Cleaned up {count} expired idempotency records")
        return count


class IdempotencyConflictError(Exception):
    """Raised when request hash doesn't match for same idempotency key"""
    pass


class IdempotencyInProgressError(Exception):
    """Raised when transaction is already being processed"""
    pass


# Decorator for idempotent workflow execution
def idempotent_transaction(key_extractor):
    """
    Decorator to make workflow execution idempotent
    
    Usage:
        @idempotent_transaction(lambda input: f"cash_in:{input.transaction_id}")
        async def run(self, input: TransactionInput) -> Dict[str, Any]:
            ...
    """
    def decorator(func):
        async def wrapper(self, input, *args, **kwargs):
            idempotency_service = getattr(self, '_idempotency_service', None)
            if not idempotency_service:
                # No idempotency service configured, run normally
                return await func(self, input, *args, **kwargs)
            
            idempotency_key = key_extractor(input)
            request_data = input.__dict__ if hasattr(input, '__dict__') else dict(input)
            
            # Check existing
            existing = await idempotency_service.check(idempotency_key, request_data)
            if existing:
                if existing.status == TransactionIdempotencyStatus.COMPLETED:
                    return existing.response
                if existing.status == TransactionIdempotencyStatus.PROCESSING:
                    raise IdempotencyInProgressError(
                        f"Transaction {idempotency_key} is already being processed"
                    )
                if existing.status == TransactionIdempotencyStatus.FAILED:
                    # Allow retry of failed transactions
                    pass
            
            # Start processing
            transaction_id = getattr(input, 'transaction_id', idempotency_key)
            acquired = await idempotency_service.start(
                idempotency_key, request_data, transaction_id
            )
            
            if not acquired:
                raise IdempotencyInProgressError(
                    f"Transaction {idempotency_key} is already being processed"
                )
            
            try:
                result = await func(self, input, *args, **kwargs)
                await idempotency_service.complete(idempotency_key, result)
                return result
            except Exception as e:
                await idempotency_service.fail(idempotency_key, str(e))
                raise
        
        return wrapper
    return decorator
