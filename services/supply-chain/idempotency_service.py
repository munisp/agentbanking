"""
Idempotency Service
Ensures operations are executed exactly once using idempotency keys
Prevents duplicate transactions, orders, and shipments
"""

import os
import json
import uuid
import hashlib
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import asyncpg
import redis.asyncio as redis

logger = logging.getLogger(__name__)

T = TypeVar('T')


class IdempotencyStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IdempotencyRecord:
    idempotency_key: str
    operation_type: str
    status: IdempotencyStatus
    request_hash: str
    response: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    error: Optional[str] = None
    lock_token: Optional[str] = None


class IdempotencyStore:
    """Abstract base for idempotency storage"""
    
    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        raise NotImplementedError
    
    async def create(self, record: IdempotencyRecord) -> bool:
        raise NotImplementedError
    
    async def update(self, record: IdempotencyRecord) -> bool:
        raise NotImplementedError
    
    async def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    async def acquire_lock(self, key: str, timeout_seconds: int = 30) -> Optional[str]:
        raise NotImplementedError
    
    async def release_lock(self, key: str, lock_token: str) -> bool:
        raise NotImplementedError


class PostgresIdempotencyStore(IdempotencyStore):
    """PostgreSQL-based idempotency store"""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def initialize_schema(self):
        """Create idempotency table if it doesn't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    idempotency_key VARCHAR(255) PRIMARY KEY,
                    operation_type VARCHAR(100) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    request_hash VARCHAR(64) NOT NULL,
                    response JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    error TEXT,
                    lock_token VARCHAR(64)
                );
                
                CREATE INDEX IF NOT EXISTS idx_idempotency_expires 
                ON idempotency_records(expires_at);
                
                CREATE INDEX IF NOT EXISTS idx_idempotency_status 
                ON idempotency_records(status);
            """)
    
    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Get idempotency record by key"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM idempotency_records WHERE idempotency_key = $1",
                key
            )
            
            if not row:
                return None
            
            return IdempotencyRecord(
                idempotency_key=row['idempotency_key'],
                operation_type=row['operation_type'],
                status=IdempotencyStatus(row['status']),
                request_hash=row['request_hash'],
                response=json.loads(row['response']) if row['response'] else None,
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                expires_at=row['expires_at'],
                error=row['error'],
                lock_token=row['lock_token']
            )
    
    async def create(self, record: IdempotencyRecord) -> bool:
        """Create new idempotency record"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO idempotency_records (
                        idempotency_key, operation_type, status, request_hash,
                        response, created_at, updated_at, expires_at, error, lock_token
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                    record.idempotency_key,
                    record.operation_type,
                    record.status.value,
                    record.request_hash,
                    json.dumps(record.response) if record.response else None,
                    record.created_at,
                    record.updated_at,
                    record.expires_at,
                    record.error,
                    record.lock_token
                )
                return True
        except asyncpg.UniqueViolationError:
            return False
    
    async def update(self, record: IdempotencyRecord) -> bool:
        """Update idempotency record"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE idempotency_records
                SET status = $2, response = $3, updated_at = $4, error = $5, lock_token = $6
                WHERE idempotency_key = $1
            """,
                record.idempotency_key,
                record.status.value,
                json.dumps(record.response) if record.response else None,
                datetime.utcnow(),
                record.error,
                record.lock_token
            )
            return result == "UPDATE 1"
    
    async def delete(self, key: str) -> bool:
        """Delete idempotency record"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM idempotency_records WHERE idempotency_key = $1",
                key
            )
            return result == "DELETE 1"
    
    async def acquire_lock(self, key: str, timeout_seconds: int = 30) -> Optional[str]:
        """Acquire lock on idempotency key using advisory lock"""
        lock_token = str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            key_hash = int(hashlib.sha256(key.encode()).hexdigest()[:15], 16)
            
            acquired = await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)",
                key_hash
            )
            
            if acquired:
                await conn.execute("""
                    UPDATE idempotency_records
                    SET lock_token = $2
                    WHERE idempotency_key = $1
                """, key, lock_token)
                
                return lock_token
            
            return None
    
    async def release_lock(self, key: str, lock_token: str) -> bool:
        """Release lock on idempotency key"""
        async with self.pool.acquire() as conn:
            key_hash = int(hashlib.sha256(key.encode()).hexdigest()[:15], 16)
            
            await conn.execute("""
                UPDATE idempotency_records
                SET lock_token = NULL
                WHERE idempotency_key = $1 AND lock_token = $2
            """, key, lock_token)
            
            await conn.execute("SELECT pg_advisory_unlock($1)", key_hash)
            
            return True
    
    async def cleanup_expired(self) -> int:
        """Remove expired idempotency records"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM idempotency_records
                WHERE expires_at < NOW()
            """)
            
            count = int(result.split()[-1]) if result else 0
            logger.info(f"Cleaned up {count} expired idempotency records")
            return count


class RedisIdempotencyStore(IdempotencyStore):
    """Redis-based idempotency store for high-performance scenarios"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.key_prefix = "idempotency:"
        self.lock_prefix = "idempotency_lock:"
    
    def _key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"
    
    def _lock_key(self, key: str) -> str:
        return f"{self.lock_prefix}{key}"
    
    async def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Get idempotency record from Redis"""
        data = await self.redis.get(self._key(key))
        
        if not data:
            return None
        
        record_dict = json.loads(data)
        
        return IdempotencyRecord(
            idempotency_key=record_dict['idempotency_key'],
            operation_type=record_dict['operation_type'],
            status=IdempotencyStatus(record_dict['status']),
            request_hash=record_dict['request_hash'],
            response=record_dict.get('response'),
            created_at=datetime.fromisoformat(record_dict['created_at']),
            updated_at=datetime.fromisoformat(record_dict['updated_at']),
            expires_at=datetime.fromisoformat(record_dict['expires_at']),
            error=record_dict.get('error'),
            lock_token=record_dict.get('lock_token')
        )
    
    async def create(self, record: IdempotencyRecord) -> bool:
        """Create new idempotency record in Redis"""
        key = self._key(record.idempotency_key)
        
        record_dict = {
            'idempotency_key': record.idempotency_key,
            'operation_type': record.operation_type,
            'status': record.status.value,
            'request_hash': record.request_hash,
            'response': record.response,
            'created_at': record.created_at.isoformat(),
            'updated_at': record.updated_at.isoformat(),
            'expires_at': record.expires_at.isoformat(),
            'error': record.error,
            'lock_token': record.lock_token
        }
        
        ttl = int((record.expires_at - datetime.utcnow()).total_seconds())
        if ttl <= 0:
            ttl = 3600
        
        result = await self.redis.set(
            key,
            json.dumps(record_dict),
            nx=True,
            ex=ttl
        )
        
        return result is not None
    
    async def update(self, record: IdempotencyRecord) -> bool:
        """Update idempotency record in Redis"""
        key = self._key(record.idempotency_key)
        
        record.updated_at = datetime.utcnow()
        
        record_dict = {
            'idempotency_key': record.idempotency_key,
            'operation_type': record.operation_type,
            'status': record.status.value,
            'request_hash': record.request_hash,
            'response': record.response,
            'created_at': record.created_at.isoformat(),
            'updated_at': record.updated_at.isoformat(),
            'expires_at': record.expires_at.isoformat(),
            'error': record.error,
            'lock_token': record.lock_token
        }
        
        ttl = int((record.expires_at - datetime.utcnow()).total_seconds())
        if ttl <= 0:
            ttl = 3600
        
        await self.redis.set(key, json.dumps(record_dict), ex=ttl)
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete idempotency record from Redis"""
        result = await self.redis.delete(self._key(key))
        return result > 0
    
    async def acquire_lock(self, key: str, timeout_seconds: int = 30) -> Optional[str]:
        """Acquire distributed lock using Redis"""
        lock_token = str(uuid.uuid4())
        lock_key = self._lock_key(key)
        
        acquired = await self.redis.set(
            lock_key,
            lock_token,
            nx=True,
            ex=timeout_seconds
        )
        
        if acquired:
            return lock_token
        
        return None
    
    async def release_lock(self, key: str, lock_token: str) -> bool:
        """Release distributed lock"""
        lock_key = self._lock_key(key)
        
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        result = await self.redis.eval(script, 1, lock_key, lock_token)
        return result == 1


class IdempotencyService:
    """Service for handling idempotent operations"""
    
    def __init__(
        self,
        store: IdempotencyStore,
        default_ttl_hours: int = 24
    ):
        self.store = store
        self.default_ttl_hours = default_ttl_hours
    
    def generate_key(self, operation_type: str, *args, **kwargs) -> str:
        """Generate idempotency key from operation and parameters"""
        key_parts = [operation_type]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        
        key_string = ":".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def hash_request(self, request: Dict[str, Any]) -> str:
        """Generate hash of request payload"""
        request_string = json.dumps(request, sort_keys=True, default=str)
        return hashlib.sha256(request_string.encode()).hexdigest()
    
    async def execute_idempotent(
        self,
        idempotency_key: str,
        operation_type: str,
        request: Dict[str, Any],
        operation: Callable[[], Awaitable[Dict[str, Any]]],
        ttl_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute operation idempotently"""
        request_hash = self.hash_request(request)
        ttl = ttl_hours or self.default_ttl_hours
        
        existing = await self.store.get(idempotency_key)
        
        if existing:
            if existing.request_hash != request_hash:
                raise ValueError(
                    f"Idempotency key {idempotency_key} already used with different request"
                )
            
            if existing.status == IdempotencyStatus.COMPLETED:
                logger.info(f"Returning cached response for {idempotency_key}")
                return existing.response or {}
            
            if existing.status == IdempotencyStatus.FAILED:
                raise ValueError(f"Previous operation failed: {existing.error}")
            
            if existing.status == IdempotencyStatus.PROCESSING:
                for _ in range(30):
                    await asyncio.sleep(1)
                    existing = await self.store.get(idempotency_key)
                    if existing and existing.status == IdempotencyStatus.COMPLETED:
                        return existing.response or {}
                    if existing and existing.status == IdempotencyStatus.FAILED:
                        raise ValueError(f"Operation failed: {existing.error}")
                
                raise TimeoutError(f"Operation {idempotency_key} timed out")
        
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            operation_type=operation_type,
            status=IdempotencyStatus.PENDING,
            request_hash=request_hash,
            response=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=ttl)
        )
        
        created = await self.store.create(record)
        
        if not created:
            return await self.execute_idempotent(
                idempotency_key, operation_type, request, operation, ttl_hours
            )
        
        lock_token = await self.store.acquire_lock(idempotency_key)
        if not lock_token:
            return await self.execute_idempotent(
                idempotency_key, operation_type, request, operation, ttl_hours
            )
        
        try:
            record.status = IdempotencyStatus.PROCESSING
            record.lock_token = lock_token
            await self.store.update(record)
            
            logger.info(f"Executing operation {operation_type} with key {idempotency_key}")
            
            result = await operation()
            
            record.status = IdempotencyStatus.COMPLETED
            record.response = result
            await self.store.update(record)
            
            logger.info(f"Operation {idempotency_key} completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Operation {idempotency_key} failed: {e}")
            
            record.status = IdempotencyStatus.FAILED
            record.error = str(e)
            await self.store.update(record)
            
            raise
            
        finally:
            await self.store.release_lock(idempotency_key, lock_token)
    
    async def get_status(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get status of idempotent operation"""
        record = await self.store.get(idempotency_key)
        
        if not record:
            return None
        
        return {
            "idempotency_key": record.idempotency_key,
            "operation_type": record.operation_type,
            "status": record.status.value,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "has_response": record.response is not None,
            "error": record.error
        }
    
    async def invalidate(self, idempotency_key: str) -> bool:
        """Invalidate an idempotency key (use with caution)"""
        return await self.store.delete(idempotency_key)


def idempotent(
    operation_type: str,
    key_params: Optional[list] = None,
    ttl_hours: int = 24
):
    """Decorator for making functions idempotent"""
    def decorator(func: Callable[..., Awaitable[Dict[str, Any]]]):
        async def wrapper(
            self,
            *args,
            idempotency_key: Optional[str] = None,
            idempotency_service: Optional[IdempotencyService] = None,
            **kwargs
        ):
            if not idempotency_service:
                return await func(self, *args, **kwargs)
            
            if not idempotency_key:
                if key_params:
                    key_values = [kwargs.get(p) or args[i] if i < len(args) else None 
                                  for i, p in enumerate(key_params)]
                    idempotency_key = idempotency_service.generate_key(
                        operation_type, *key_values
                    )
                else:
                    idempotency_key = idempotency_service.generate_key(
                        operation_type, *args, **kwargs
                    )
            
            request = {"args": args, "kwargs": kwargs}
            
            return await idempotency_service.execute_idempotent(
                idempotency_key=idempotency_key,
                operation_type=operation_type,
                request=request,
                operation=lambda: func(self, *args, **kwargs),
                ttl_hours=ttl_hours
            )
        
        return wrapper
    return decorator
