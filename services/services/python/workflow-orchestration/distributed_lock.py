"""
Distributed Locking for Concurrent Transaction Prevention

Provides distributed locking to prevent:
- Race conditions on concurrent transactions
- Double-spending attacks
- Concurrent float modifications
- Parallel transaction processing for same customer/agent pair
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class LockInfo:
    key: str
    owner: str
    acquired_at: datetime
    expires_at: datetime
    transaction_id: Optional[str] = None


class DistributedLockError(Exception):
    """Base exception for distributed lock errors"""
    pass


class LockAcquisitionError(DistributedLockError):
    """Raised when lock cannot be acquired"""
    pass


class LockNotHeldError(DistributedLockError):
    """Raised when trying to release a lock not held"""
    pass


class TransactionDistributedLock:
    """
    Redis-based distributed lock for financial transactions
    
    Features:
    - Atomic lock acquisition with Lua scripts
    - Automatic expiry to prevent deadlocks
    - Lock extension for long-running transactions
    - Owner verification for safe release
    - Transaction-specific locking strategies
    """
    
    LOCK_PREFIX = "txn:lock:"
    DEFAULT_TTL_SECONDS = 30
    RETRY_DELAY_MS = 50
    MAX_RETRIES = 20
    
    # Lua script for atomic lock acquisition
    ACQUIRE_SCRIPT = """
    local key = KEYS[1]
    local owner = ARGV[1]
    local ttl = tonumber(ARGV[2])
    local transaction_id = ARGV[3]
    
    -- Check if lock exists
    local current_owner = redis.call('HGET', key, 'owner')
    
    if current_owner == false then
        -- Lock doesn't exist, acquire it
        redis.call('HSET', key, 'owner', owner)
        redis.call('HSET', key, 'transaction_id', transaction_id)
        redis.call('HSET', key, 'acquired_at', ARGV[4])
        redis.call('EXPIRE', key, ttl)
        return 1
    elseif current_owner == owner then
        -- We already own the lock, extend it
        redis.call('EXPIRE', key, ttl)
        return 1
    else
        -- Lock is held by someone else
        return 0
    end
    """
    
    # Lua script for atomic lock release
    RELEASE_SCRIPT = """
    local key = KEYS[1]
    local owner = ARGV[1]
    
    local current_owner = redis.call('HGET', key, 'owner')
    
    if current_owner == owner then
        redis.call('DEL', key)
        return 1
    else
        return 0
    end
    """
    
    # Lua script for lock extension
    EXTEND_SCRIPT = """
    local key = KEYS[1]
    local owner = ARGV[1]
    local ttl = tonumber(ARGV[2])
    
    local current_owner = redis.call('HGET', key, 'owner')
    
    if current_owner == owner then
        redis.call('EXPIRE', key, ttl)
        return 1
    else
        return 0
    end
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        ttl_seconds: int = DEFAULT_TTL_SECONDS
    ):
        self.redis = redis_client
        self.ttl = ttl_seconds
        self._owner_id = str(uuid.uuid4())
        self._acquire_sha: Optional[str] = None
        self._release_sha: Optional[str] = None
        self._extend_sha: Optional[str] = None
    
    async def initialize(self):
        """Load Lua scripts into Redis"""
        self._acquire_sha = await self.redis.script_load(self.ACQUIRE_SCRIPT)
        self._release_sha = await self.redis.script_load(self.RELEASE_SCRIPT)
        self._extend_sha = await self.redis.script_load(self.EXTEND_SCRIPT)
        logger.info("Distributed lock Lua scripts loaded")
    
    def _lock_key(self, key: str) -> str:
        """Generate full lock key"""
        return f"{self.LOCK_PREFIX}{key}"
    
    async def acquire(
        self,
        key: str,
        transaction_id: Optional[str] = None,
        timeout_seconds: float = 10.0,
        ttl_seconds: Optional[int] = None
    ) -> LockInfo:
        """
        Acquire a distributed lock
        
        Args:
            key: Lock key (e.g., "agent:123:customer:456")
            transaction_id: Associated transaction ID
            timeout_seconds: Max time to wait for lock
            ttl_seconds: Lock TTL (default: 30 seconds)
            
        Returns:
            LockInfo with lock details
            
        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        lock_key = self._lock_key(key)
        ttl = ttl_seconds or self.ttl
        acquired_at = datetime.utcnow()
        
        start_time = time.time()
        retries = 0
        
        while time.time() - start_time < timeout_seconds:
            result = await self.redis.evalsha(
                self._acquire_sha,
                1,
                lock_key,
                self._owner_id,
                ttl,
                transaction_id or "",
                acquired_at.isoformat()
            )
            
            if result == 1:
                logger.info(f"Acquired lock: {key} (owner={self._owner_id[:8]})")
                return LockInfo(
                    key=key,
                    owner=self._owner_id,
                    acquired_at=acquired_at,
                    expires_at=acquired_at + timedelta(seconds=ttl),
                    transaction_id=transaction_id
                )
            
            retries += 1
            if retries >= self.MAX_RETRIES:
                break
            
            await asyncio.sleep(self.RETRY_DELAY_MS / 1000)
        
        # Get info about who holds the lock
        lock_info = await self.redis.hgetall(lock_key)
        holder = lock_info.get("owner", "unknown")[:8] if lock_info else "unknown"
        
        raise LockAcquisitionError(
            f"Failed to acquire lock '{key}' after {timeout_seconds}s. "
            f"Currently held by: {holder}"
        )
    
    async def release(self, key: str) -> bool:
        """
        Release a distributed lock
        
        Args:
            key: Lock key to release
            
        Returns:
            True if released, False if not held
        """
        lock_key = self._lock_key(key)
        
        result = await self.redis.evalsha(
            self._release_sha,
            1,
            lock_key,
            self._owner_id
        )
        
        if result == 1:
            logger.info(f"Released lock: {key}")
            return True
        else:
            logger.warning(f"Failed to release lock: {key} (not held)")
            return False
    
    async def extend(
        self,
        key: str,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Extend lock TTL
        
        Args:
            key: Lock key to extend
            ttl_seconds: New TTL (default: original TTL)
            
        Returns:
            True if extended, False if not held
        """
        lock_key = self._lock_key(key)
        ttl = ttl_seconds or self.ttl
        
        result = await self.redis.evalsha(
            self._extend_sha,
            1,
            lock_key,
            self._owner_id,
            ttl
        )
        
        if result == 1:
            logger.debug(f"Extended lock: {key} by {ttl}s")
            return True
        else:
            logger.warning(f"Failed to extend lock: {key} (not held)")
            return False
    
    async def is_locked(self, key: str) -> bool:
        """Check if a key is locked"""
        lock_key = self._lock_key(key)
        return await self.redis.exists(lock_key) > 0
    
    async def get_lock_info(self, key: str) -> Optional[LockInfo]:
        """Get information about a lock"""
        lock_key = self._lock_key(key)
        data = await self.redis.hgetall(lock_key)
        
        if not data:
            return None
        
        ttl = await self.redis.ttl(lock_key)
        
        return LockInfo(
            key=key,
            owner=data.get("owner", ""),
            acquired_at=datetime.fromisoformat(data.get("acquired_at", datetime.utcnow().isoformat())),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else datetime.utcnow(),
            transaction_id=data.get("transaction_id")
        )


class TransactionLockManager:
    """
    High-level lock manager for transaction workflows
    
    Provides transaction-specific locking strategies:
    - Agent float lock
    - Customer balance lock
    - Agent-customer pair lock
    - Daily limit lock
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.lock = TransactionDistributedLock(redis_client)
    
    async def initialize(self):
        """Initialize lock manager"""
        await self.lock.initialize()
    
    async def acquire_cash_in_locks(
        self,
        agent_id: str,
        customer_id: str,
        transaction_id: str,
        timeout_seconds: float = 10.0
    ) -> Dict[str, LockInfo]:
        """
        Acquire all locks needed for cash-in transaction
        
        Locks:
        1. Agent float lock (prevent concurrent float modifications)
        2. Customer balance lock (prevent concurrent balance modifications)
        3. Agent-customer pair lock (prevent duplicate transactions)
        """
        locks = {}
        
        try:
            # Lock agent float
            locks["agent_float"] = await self.lock.acquire(
                f"agent:float:{agent_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            # Lock customer balance
            locks["customer_balance"] = await self.lock.acquire(
                f"customer:balance:{customer_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            # Lock agent-customer pair
            locks["pair"] = await self.lock.acquire(
                f"pair:{agent_id}:{customer_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            logger.info(
                f"Acquired cash-in locks for transaction {transaction_id}"
            )
            return locks
            
        except LockAcquisitionError:
            # Release any acquired locks
            await self.release_locks(locks)
            raise
    
    async def acquire_cash_out_locks(
        self,
        agent_id: str,
        customer_id: str,
        transaction_id: str,
        timeout_seconds: float = 10.0
    ) -> Dict[str, LockInfo]:
        """
        Acquire all locks needed for cash-out transaction
        
        Locks:
        1. Customer balance lock (prevent concurrent balance modifications)
        2. Agent cash lock (prevent concurrent cash modifications)
        3. Agent-customer pair lock (prevent duplicate transactions)
        """
        locks = {}
        
        try:
            # Lock customer balance first (debit side)
            locks["customer_balance"] = await self.lock.acquire(
                f"customer:balance:{customer_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            # Lock agent cash
            locks["agent_cash"] = await self.lock.acquire(
                f"agent:cash:{agent_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            # Lock agent-customer pair
            locks["pair"] = await self.lock.acquire(
                f"pair:{agent_id}:{customer_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            logger.info(
                f"Acquired cash-out locks for transaction {transaction_id}"
            )
            return locks
            
        except LockAcquisitionError:
            await self.release_locks(locks)
            raise
    
    async def acquire_transfer_locks(
        self,
        from_customer_id: str,
        to_customer_id: str,
        transaction_id: str,
        timeout_seconds: float = 10.0
    ) -> Dict[str, LockInfo]:
        """
        Acquire locks for P2P transfer
        
        Uses consistent ordering to prevent deadlocks
        """
        locks = {}
        
        # Order by customer ID to prevent deadlocks
        first_id, second_id = sorted([from_customer_id, to_customer_id])
        
        try:
            locks["first_balance"] = await self.lock.acquire(
                f"customer:balance:{first_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            locks["second_balance"] = await self.lock.acquire(
                f"customer:balance:{second_id}",
                transaction_id=transaction_id,
                timeout_seconds=timeout_seconds
            )
            
            logger.info(
                f"Acquired transfer locks for transaction {transaction_id}"
            )
            return locks
            
        except LockAcquisitionError:
            await self.release_locks(locks)
            raise
    
    async def release_locks(self, locks: Dict[str, LockInfo]):
        """Release all locks in a lock set"""
        for name, lock_info in locks.items():
            try:
                await self.lock.release(lock_info.key)
            except Exception as e:
                logger.error(f"Failed to release lock {name}: {e}")
    
    async def extend_locks(
        self,
        locks: Dict[str, LockInfo],
        ttl_seconds: int = 30
    ):
        """Extend all locks in a lock set"""
        for name, lock_info in locks.items():
            try:
                await self.lock.extend(lock_info.key, ttl_seconds)
            except Exception as e:
                logger.error(f"Failed to extend lock {name}: {e}")


# Context manager for automatic lock management
class TransactionLockContext:
    """
    Context manager for transaction locks
    
    Usage:
        async with TransactionLockContext(manager, "cash_in", agent_id, customer_id, txn_id) as locks:
            # Perform transaction
            pass
        # Locks automatically released
    """
    
    def __init__(
        self,
        manager: TransactionLockManager,
        transaction_type: str,
        agent_id: str,
        customer_id: str,
        transaction_id: str,
        timeout_seconds: float = 10.0
    ):
        self.manager = manager
        self.transaction_type = transaction_type
        self.agent_id = agent_id
        self.customer_id = customer_id
        self.transaction_id = transaction_id
        self.timeout = timeout_seconds
        self.locks: Dict[str, LockInfo] = {}
    
    async def __aenter__(self) -> Dict[str, LockInfo]:
        if self.transaction_type == "cash_in":
            self.locks = await self.manager.acquire_cash_in_locks(
                self.agent_id,
                self.customer_id,
                self.transaction_id,
                self.timeout
            )
        elif self.transaction_type == "cash_out":
            self.locks = await self.manager.acquire_cash_out_locks(
                self.agent_id,
                self.customer_id,
                self.transaction_id,
                self.timeout
            )
        else:
            raise ValueError(f"Unknown transaction type: {self.transaction_type}")
        
        return self.locks
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.manager.release_locks(self.locks)
        return False


# Global lock manager instance
_lock_manager: Optional[TransactionLockManager] = None


async def get_lock_manager() -> TransactionLockManager:
    """Get or create global lock manager"""
    global _lock_manager
    
    if _lock_manager is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable not set")
        
        redis_client = redis.from_url(redis_url)
        _lock_manager = TransactionLockManager(redis_client)
        await _lock_manager.initialize()
    
    return _lock_manager
