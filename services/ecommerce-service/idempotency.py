"""
Idempotency Module
Implements idempotency keys for order creation and other critical operations
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Callable, TypeVar
from functools import wraps
import redis.asyncio as redis
import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar('T')


class IdempotencyStatus(str, Enum):
    """Idempotency request status"""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IdempotencyRecord:
    """Idempotency record"""
    key: str
    status: IdempotencyStatus
    request_hash: str
    response: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    expires_at: datetime


class IdempotencyService:
    """
    Idempotency service for ensuring exactly-once semantics
    
    Features:
    - Prevents duplicate order creation
    - Stores responses for replay
    - Configurable TTL for idempotency keys
    - Request hash validation to detect mismatched requests
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        db_pool: Optional[asyncpg.Pool] = None,
        default_ttl_hours: int = 24
    ):
        self.redis = redis_client
        self.db_pool = db_pool
        self.default_ttl = timedelta(hours=default_ttl_hours)
    
    async def initialize(self):
        """Initialize idempotency service"""
        if self.db_pool:
            await self._ensure_tables()
        logger.info("Idempotency service initialized")
    
    async def _ensure_tables(self):
        """Ensure idempotency tables exist"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key VARCHAR(255) PRIMARY KEY,
                    status VARCHAR(20) NOT NULL,
                    request_hash VARCHAR(64) NOT NULL,
                    response JSONB,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_idempotency_expires 
                ON idempotency_keys(expires_at)
            """)
    
    def _hash_request(self, request_data: Dict[str, Any]) -> str:
        """Generate hash of request data for validation"""
        # Sort keys for consistent hashing
        serialized = json.dumps(request_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    async def check(
        self,
        idempotency_key: str,
        request_data: Dict[str, Any]
    ) -> Optional[IdempotencyRecord]:
        """
        Check if idempotency key exists and validate request
        
        Args:
            idempotency_key: Unique idempotency key from client
            request_data: Request data to hash and validate
        
        Returns:
            IdempotencyRecord if key exists, None otherwise
        
        Raises:
            IdempotencyConflictError: If key exists with different request data
        """
        request_hash = self._hash_request(request_data)
        
        # Check Redis first (fast path)
        cached = await self.redis.hgetall(f"idempotency:{idempotency_key}")
        
        if cached:
            stored_hash = cached.get("request_hash", "")
            if stored_hash and stored_hash != request_hash:
                raise IdempotencyConflictError(
                    f"Idempotency key {idempotency_key} already used with different request"
                )
            
            status = IdempotencyStatus(cached.get("status", "processing"))
            
            if status == IdempotencyStatus.COMPLETED:
                response = json.loads(cached.get("response", "null"))
                return IdempotencyRecord(
                    key=idempotency_key,
                    status=status,
                    request_hash=stored_hash,
                    response=response,
                    error=None,
                    created_at=datetime.fromisoformat(cached.get("created_at", datetime.utcnow().isoformat())),
                    expires_at=datetime.fromisoformat(cached.get("expires_at", (datetime.utcnow() + self.default_ttl).isoformat()))
                )
            
            if status == IdempotencyStatus.FAILED:
                error = cached.get("error", "Unknown error")
                return IdempotencyRecord(
                    key=idempotency_key,
                    status=status,
                    request_hash=stored_hash,
                    response=None,
                    error=error,
                    created_at=datetime.fromisoformat(cached.get("created_at", datetime.utcnow().isoformat())),
                    expires_at=datetime.fromisoformat(cached.get("expires_at", (datetime.utcnow() + self.default_ttl).isoformat()))
                )
            
            # Still processing - return record to indicate in-progress
            return IdempotencyRecord(
                key=idempotency_key,
                status=status,
                request_hash=stored_hash,
                response=None,
                error=None,
                created_at=datetime.fromisoformat(cached.get("created_at", datetime.utcnow().isoformat())),
                expires_at=datetime.fromisoformat(cached.get("expires_at", (datetime.utcnow() + self.default_ttl).isoformat()))
            )
        
        return None
    
    async def start(
        self,
        idempotency_key: str,
        request_data: Dict[str, Any],
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Start processing with idempotency key
        
        Args:
            idempotency_key: Unique idempotency key
            request_data: Request data to hash
            ttl: Time-to-live for the key
        
        Returns:
            True if successfully acquired, False if key already exists
        """
        ttl = ttl or self.default_ttl
        request_hash = self._hash_request(request_data)
        now = datetime.utcnow()
        expires_at = now + ttl
        
        # Use Redis SETNX for atomic check-and-set
        acquired = await self.redis.hsetnx(
            f"idempotency:{idempotency_key}",
            "status",
            IdempotencyStatus.PROCESSING.value
        )
        
        if not acquired:
            return False
        
        # Set remaining fields
        await self.redis.hset(
            f"idempotency:{idempotency_key}",
            mapping={
                "request_hash": request_hash,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat()
            }
        )
        
        # Set expiry
        await self.redis.expire(
            f"idempotency:{idempotency_key}",
            int(ttl.total_seconds())
        )
        
        # Persist to database if available
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO idempotency_keys (key, status, request_hash, expires_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (key) DO NOTHING
                    """, idempotency_key, IdempotencyStatus.PROCESSING.value, request_hash, expires_at)
            except Exception as e:
                logger.error(f"Failed to persist idempotency key: {e}")
        
        return True
    
    async def complete(
        self,
        idempotency_key: str,
        response: Dict[str, Any]
    ):
        """
        Mark idempotency key as completed with response
        
        Args:
            idempotency_key: Idempotency key
            response: Response to store for replay
        """
        await self.redis.hset(
            f"idempotency:{idempotency_key}",
            mapping={
                "status": IdempotencyStatus.COMPLETED.value,
                "response": json.dumps(response, default=str)
            }
        )
        
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE idempotency_keys
                        SET status = $1, response = $2
                        WHERE key = $3
                    """, IdempotencyStatus.COMPLETED.value, json.dumps(response, default=str), idempotency_key)
            except Exception as e:
                logger.error(f"Failed to update idempotency key: {e}")
    
    async def fail(
        self,
        idempotency_key: str,
        error: str
    ):
        """
        Mark idempotency key as failed
        
        Args:
            idempotency_key: Idempotency key
            error: Error message
        """
        await self.redis.hset(
            f"idempotency:{idempotency_key}",
            mapping={
                "status": IdempotencyStatus.FAILED.value,
                "error": error
            }
        )
        
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE idempotency_keys
                        SET status = $1, error = $2
                        WHERE key = $3
                    """, IdempotencyStatus.FAILED.value, error, idempotency_key)
            except Exception as e:
                logger.error(f"Failed to update idempotency key: {e}")
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired idempotency keys from database
        
        Returns:
            Number of keys cleaned up
        """
        if not self.db_pool:
            return 0
        
        async with self.db_pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM idempotency_keys
                WHERE expires_at < NOW()
            """)
            count = int(result.split()[-1]) if result else 0
            
        if count > 0:
            logger.info(f"Cleaned up {count} expired idempotency keys")
        
        return count


class IdempotencyConflictError(Exception):
    """Raised when idempotency key is reused with different request"""
    pass


class IdempotencyInProgressError(Exception):
    """Raised when request is still being processed"""
    pass


def idempotent(
    key_extractor: Callable[..., str],
    request_extractor: Optional[Callable[..., Dict[str, Any]]] = None
):
    """
    Decorator for idempotent operations
    
    Args:
        key_extractor: Function to extract idempotency key from arguments
        request_extractor: Function to extract request data for hashing
    
    Usage:
        @idempotent(
            key_extractor=lambda order_request: order_request.idempotency_key,
            request_extractor=lambda order_request: order_request.dict()
        )
        async def create_order(order_request: OrderRequest) -> Order:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, idempotency_service: IdempotencyService, **kwargs) -> T:
            # Extract idempotency key
            idempotency_key = key_extractor(*args, **kwargs)
            
            # Extract request data for hashing
            if request_extractor:
                request_data = request_extractor(*args, **kwargs)
            else:
                request_data = {"args": str(args), "kwargs": str(kwargs)}
            
            # Check for existing record
            existing = await idempotency_service.check(idempotency_key, request_data)
            
            if existing:
                if existing.status == IdempotencyStatus.COMPLETED:
                    logger.info(f"Returning cached response for idempotency key {idempotency_key}")
                    return existing.response
                
                if existing.status == IdempotencyStatus.FAILED:
                    raise Exception(existing.error)
                
                if existing.status == IdempotencyStatus.PROCESSING:
                    raise IdempotencyInProgressError(
                        f"Request with idempotency key {idempotency_key} is still processing"
                    )
            
            # Start processing
            acquired = await idempotency_service.start(idempotency_key, request_data)
            if not acquired:
                raise IdempotencyInProgressError(
                    f"Request with idempotency key {idempotency_key} is already processing"
                )
            
            try:
                result = await func(*args, **kwargs)
                await idempotency_service.complete(idempotency_key, result)
                return result
            except Exception as e:
                await idempotency_service.fail(idempotency_key, str(e))
                raise
        
        return wrapper
    return decorator
