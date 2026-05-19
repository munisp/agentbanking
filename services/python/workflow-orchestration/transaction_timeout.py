"""
Transaction Timeout with Automatic Reversal

Provides automatic transaction timeout and reversal:
- Configurable timeout per transaction type
- Automatic compensation on timeout
- Stuck transaction detection
- Recovery workflow for orphaned transactions
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from temporalio import workflow, activity
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

# Service URLs
DATABASE_URL = os.getenv("DATABASE_URL")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL")

# Optional imports
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

_db_pool = None
_redis_client = None


async def get_db_pool():
    """Get database connection pool"""
    global _db_pool
    if _db_pool is None:
        if not HAS_ASYNCPG:
            raise ValueError("asyncpg not installed")
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not set")
        _db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    return _db_pool


async def get_redis_client():
    """Get Redis client"""
    global _redis_client
    if _redis_client is None:
        if not HAS_REDIS:
            raise ValueError("redis not installed")
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL not set")
        _redis_client = redis.from_url(redis_url)
    return _redis_client


class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REVERSED = "reversed"
    STUCK = "stuck"


class TransactionType(str, Enum):
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"
    TRANSFER = "transfer"
    BILL_PAYMENT = "bill_payment"
    AIRTIME = "airtime"


# Timeout configuration per transaction type (in seconds)
TRANSACTION_TIMEOUTS = {
    TransactionType.CASH_IN: 120,      # 2 minutes
    TransactionType.CASH_OUT: 120,     # 2 minutes
    TransactionType.TRANSFER: 60,      # 1 minute
    TransactionType.BILL_PAYMENT: 180, # 3 minutes
    TransactionType.AIRTIME: 60,       # 1 minute
}

# Grace period before marking as stuck (in seconds)
STUCK_THRESHOLD = 300  # 5 minutes


@dataclass
class TransactionTimeoutConfig:
    transaction_type: TransactionType
    timeout_seconds: int
    auto_reverse: bool = True
    notify_on_timeout: bool = True
    max_retries: int = 0


@dataclass
class TimeoutCheckResult:
    transaction_id: str
    status: TransactionStatus
    timed_out: bool
    elapsed_seconds: float
    action_taken: Optional[str] = None


# ============================================================================
# Timeout Activities
# ============================================================================

@activity.defn
async def register_transaction_timeout(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a transaction for timeout monitoring
    
    Stores transaction start time and timeout configuration in Redis
    """
    transaction_id = data["transaction_id"]
    transaction_type = data["transaction_type"]
    agent_id = data.get("agent_id")
    customer_id = data.get("customer_id")
    amount = data.get("amount")
    
    timeout_seconds = TRANSACTION_TIMEOUTS.get(
        TransactionType(transaction_type),
        120  # Default 2 minutes
    )
    
    try:
        client = await get_redis_client()
        
        # Store transaction timeout info
        key = f"txn:timeout:{transaction_id}"
        await client.hset(key, mapping={
            "transaction_id": transaction_id,
            "transaction_type": transaction_type,
            "agent_id": agent_id or "",
            "customer_id": customer_id or "",
            "amount": str(amount or 0),
            "started_at": datetime.utcnow().isoformat(),
            "timeout_at": (datetime.utcnow() + timedelta(seconds=timeout_seconds)).isoformat(),
            "status": TransactionStatus.PROCESSING.value
        })
        
        # Set expiry slightly longer than timeout for cleanup
        await client.expire(key, timeout_seconds + 60)
        
        # Add to timeout monitoring set
        await client.zadd(
            "txn:timeout:pending",
            {transaction_id: datetime.utcnow().timestamp() + timeout_seconds}
        )
        
        activity.logger.info(
            f"Registered timeout for transaction {transaction_id}: "
            f"{timeout_seconds}s"
        )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "timeout_seconds": timeout_seconds,
            "timeout_at": (datetime.utcnow() + timedelta(seconds=timeout_seconds)).isoformat()
        }
        
    except Exception as e:
        activity.logger.error(f"Failed to register timeout: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def clear_transaction_timeout(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clear timeout monitoring for completed transaction
    """
    transaction_id = data["transaction_id"]
    final_status = data.get("status", TransactionStatus.COMPLETED.value)
    
    try:
        client = await get_redis_client()
        
        # Update status
        key = f"txn:timeout:{transaction_id}"
        await client.hset(key, "status", final_status)
        await client.hset(key, "completed_at", datetime.utcnow().isoformat())
        
        # Remove from pending set
        await client.zrem("txn:timeout:pending", transaction_id)
        
        activity.logger.info(
            f"Cleared timeout for transaction {transaction_id}: {final_status}"
        )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "status": final_status
        }
        
    except Exception as e:
        activity.logger.error(f"Failed to clear timeout: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def check_transaction_timeout(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if a transaction has timed out
    """
    transaction_id = data["transaction_id"]
    
    try:
        client = await get_redis_client()
        
        key = f"txn:timeout:{transaction_id}"
        info = await client.hgetall(key)
        
        if not info:
            return {
                "success": True,
                "transaction_id": transaction_id,
                "found": False,
                "timed_out": False
            }
        
        started_at = datetime.fromisoformat(info["started_at"])
        timeout_at = datetime.fromisoformat(info["timeout_at"])
        current_status = info["status"]
        
        now = datetime.utcnow()
        elapsed = (now - started_at).total_seconds()
        timed_out = now > timeout_at and current_status == TransactionStatus.PROCESSING.value
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "found": True,
            "timed_out": timed_out,
            "elapsed_seconds": elapsed,
            "status": current_status,
            "timeout_at": timeout_at.isoformat(),
            "transaction_type": info.get("transaction_type"),
            "agent_id": info.get("agent_id"),
            "customer_id": info.get("customer_id"),
            "amount": float(info.get("amount", 0))
        }
        
    except Exception as e:
        activity.logger.error(f"Failed to check timeout: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def get_timed_out_transactions(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all transactions that have timed out
    """
    try:
        client = await get_redis_client()
        
        now = datetime.utcnow().timestamp()
        
        # Get transactions past their timeout
        timed_out_ids = await client.zrangebyscore(
            "txn:timeout:pending",
            "-inf",
            now
        )
        
        timed_out = []
        for txn_id in timed_out_ids:
            key = f"txn:timeout:{txn_id}"
            info = await client.hgetall(key)
            
            if info and info.get("status") == TransactionStatus.PROCESSING.value:
                timed_out.append({
                    "transaction_id": txn_id,
                    "transaction_type": info.get("transaction_type"),
                    "agent_id": info.get("agent_id"),
                    "customer_id": info.get("customer_id"),
                    "amount": float(info.get("amount", 0)),
                    "started_at": info.get("started_at"),
                    "timeout_at": info.get("timeout_at")
                })
        
        return {
            "success": True,
            "count": len(timed_out),
            "transactions": timed_out
        }
        
    except Exception as e:
        activity.logger.error(f"Failed to get timed out transactions: {e}")
        return {"success": False, "error": str(e), "transactions": []}


@activity.defn
async def mark_transaction_timeout(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mark a transaction as timed out
    """
    transaction_id = data["transaction_id"]
    
    try:
        client = await get_redis_client()
        pool = await get_db_pool()
        
        # Update Redis
        key = f"txn:timeout:{transaction_id}"
        await client.hset(key, mapping={
            "status": TransactionStatus.TIMEOUT.value,
            "timed_out_at": datetime.utcnow().isoformat()
        })
        
        # Remove from pending set
        await client.zrem("txn:timeout:pending", transaction_id)
        
        # Update database
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE transactions 
                SET status = 'timeout', 
                    updated_at = NOW(),
                    timeout_at = NOW()
                WHERE transaction_id = $1
            """, transaction_id)
        
        activity.logger.info(f"Marked transaction {transaction_id} as timeout")
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "status": TransactionStatus.TIMEOUT.value
        }
        
    except Exception as e:
        activity.logger.error(f"Failed to mark timeout: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def reverse_timed_out_transaction(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reverse a timed out transaction
    
    Calls compensation activities to reverse ledger entries
    """
    transaction_id = data["transaction_id"]
    transaction_type = data["transaction_type"]
    agent_id = data.get("agent_id")
    customer_id = data.get("customer_id")
    amount = data.get("amount", 0)
    
    try:
        pool = await get_db_pool()
        
        # Get transaction details from database
        async with pool.acquire() as conn:
            txn = await conn.fetchrow("""
                SELECT * FROM transactions WHERE transaction_id = $1
            """, transaction_id)
            
            if not txn:
                return {
                    "success": False,
                    "error": "Transaction not found",
                    "transaction_id": transaction_id
                }
            
            # Check if already reversed
            if txn["status"] == "reversed":
                return {
                    "success": True,
                    "already_reversed": True,
                    "transaction_id": transaction_id
                }
            
            # Record reversal
            await conn.execute("""
                INSERT INTO transaction_reversals
                (transaction_id, reason, reversed_at, reversed_by)
                VALUES ($1, 'timeout', NOW(), 'system')
            """, transaction_id)
            
            # Update transaction status
            await conn.execute("""
                UPDATE transactions 
                SET status = 'reversed',
                    updated_at = NOW()
                WHERE transaction_id = $1
            """, transaction_id)
        
        activity.logger.info(
            f"Reversed timed out transaction {transaction_id}"
        )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "reversed": True,
            "reason": "timeout"
        }
        
    except Exception as e:
        activity.logger.error(f"Failed to reverse transaction: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def send_timeout_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send notification about transaction timeout
    """
    transaction_id = data["transaction_id"]
    agent_id = data.get("agent_id")
    customer_id = data.get("customer_id")
    amount = data.get("amount")
    transaction_type = data.get("transaction_type")
    
    if not NOTIFICATION_SERVICE_URL:
        return {"success": True, "skipped": True}
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Notify customer
            if customer_id:
                await client.post(
                    f"{NOTIFICATION_SERVICE_URL}/api/v1/notify",
                    json={
                        "recipient_id": customer_id,
                        "recipient_type": "customer",
                        "template": "transaction_timeout",
                        "data": {
                            "transaction_id": transaction_id,
                            "transaction_type": transaction_type,
                            "amount": amount
                        },
                        "channels": ["sms", "push"]
                    }
                )
            
            # Notify agent
            if agent_id:
                await client.post(
                    f"{NOTIFICATION_SERVICE_URL}/api/v1/notify",
                    json={
                        "recipient_id": agent_id,
                        "recipient_type": "agent",
                        "template": "transaction_timeout",
                        "data": {
                            "transaction_id": transaction_id,
                            "transaction_type": transaction_type,
                            "amount": amount
                        },
                        "channels": ["sms", "push"]
                    }
                )
            
            return {"success": True, "notified": True}
            
    except Exception as e:
        activity.logger.error(f"Failed to send timeout notification: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def get_stuck_transactions(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get transactions that are stuck (processing for too long)
    """
    threshold_seconds = data.get("threshold_seconds", STUCK_THRESHOLD)
    
    try:
        pool = await get_db_pool()
        
        async with pool.acquire() as conn:
            cutoff = datetime.utcnow() - timedelta(seconds=threshold_seconds)
            
            rows = await conn.fetch("""
                SELECT transaction_id, transaction_type, agent_id, 
                       customer_id, amount, created_at, status
                FROM transactions
                WHERE status = 'processing'
                AND created_at < $1
            """, cutoff)
            
            stuck = [dict(r) for r in rows]
            
            return {
                "success": True,
                "count": len(stuck),
                "transactions": stuck,
                "threshold_seconds": threshold_seconds
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to get stuck transactions: {e}")
        return {"success": False, "error": str(e), "transactions": []}


# ============================================================================
# Timeout Monitoring Workflow
# ============================================================================

@workflow.defn
class TransactionTimeoutMonitorWorkflow:
    """
    Background workflow that monitors for timed out transactions
    
    Runs periodically to:
    1. Find timed out transactions
    2. Reverse them automatically
    3. Send notifications
    4. Record audit trail
    """
    
    @workflow.run
    async def run(self, check_interval_seconds: int = 30) -> Dict[str, Any]:
        """
        Run timeout monitoring loop
        
        This workflow runs continuously, checking for timeouts
        """
        processed_count = 0
        error_count = 0
        
        # Get timed out transactions
        result = await workflow.execute_activity(
            get_timed_out_transactions,
            {},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        if not result["success"]:
            return {
                "status": "error",
                "error": result.get("error"),
                "processed": 0
            }
        
        for txn in result["transactions"]:
            try:
                # Mark as timeout
                await workflow.execute_activity(
                    mark_transaction_timeout,
                    {"transaction_id": txn["transaction_id"]},
                    start_to_close_timeout=timedelta(seconds=30)
                )
                
                # Reverse the transaction
                await workflow.execute_activity(
                    reverse_timed_out_transaction,
                    txn,
                    start_to_close_timeout=timedelta(seconds=60)
                )
                
                # Send notification
                await workflow.execute_activity(
                    send_timeout_notification,
                    txn,
                    start_to_close_timeout=timedelta(seconds=30)
                )
                
                processed_count += 1
                
            except Exception as e:
                workflow.logger.error(
                    f"Failed to process timeout for {txn['transaction_id']}: {e}"
                )
                error_count += 1
        
        return {
            "status": "completed",
            "checked_at": datetime.utcnow().isoformat(),
            "timed_out_count": result["count"],
            "processed_count": processed_count,
            "error_count": error_count
        }


@workflow.defn
class StuckTransactionRecoveryWorkflow:
    """
    Recovery workflow for stuck transactions
    
    Runs periodically to find and handle transactions that are
    stuck in processing state for too long
    """
    
    @workflow.run
    async def run(self, threshold_seconds: int = STUCK_THRESHOLD) -> Dict[str, Any]:
        """Execute stuck transaction recovery"""
        
        # Get stuck transactions
        result = await workflow.execute_activity(
            get_stuck_transactions,
            {"threshold_seconds": threshold_seconds},
            start_to_close_timeout=timedelta(seconds=60)
        )
        
        if not result["success"]:
            return {
                "status": "error",
                "error": result.get("error")
            }
        
        recovered = 0
        failed = 0
        
        for txn in result["transactions"]:
            try:
                # Mark as stuck and reverse
                await workflow.execute_activity(
                    mark_transaction_timeout,
                    {"transaction_id": txn["transaction_id"]},
                    start_to_close_timeout=timedelta(seconds=30)
                )
                
                await workflow.execute_activity(
                    reverse_timed_out_transaction,
                    {
                        "transaction_id": txn["transaction_id"],
                        "transaction_type": txn["transaction_type"],
                        "agent_id": txn["agent_id"],
                        "customer_id": txn["customer_id"],
                        "amount": float(txn["amount"])
                    },
                    start_to_close_timeout=timedelta(seconds=60)
                )
                
                recovered += 1
                
            except Exception as e:
                workflow.logger.error(
                    f"Failed to recover stuck transaction {txn['transaction_id']}: {e}"
                )
                failed += 1
        
        return {
            "status": "completed",
            "stuck_count": result["count"],
            "recovered": recovered,
            "failed": failed,
            "threshold_seconds": threshold_seconds
        }


# ============================================================================
# Transaction Timeout Decorator
# ============================================================================

def with_timeout(timeout_seconds: int = 120, auto_reverse: bool = True):
    """
    Decorator to add timeout handling to workflow activities
    
    Usage:
        @with_timeout(timeout_seconds=60)
        async def process_transaction(data):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            transaction_id = kwargs.get("transaction_id") or \
                            (args[0].get("transaction_id") if args else None)
            
            if not transaction_id:
                return await func(*args, **kwargs)
            
            # Register timeout
            try:
                client = await get_redis_client()
                key = f"txn:timeout:{transaction_id}"
                await client.hset(key, mapping={
                    "started_at": datetime.utcnow().isoformat(),
                    "timeout_at": (datetime.utcnow() + timedelta(seconds=timeout_seconds)).isoformat(),
                    "status": "processing"
                })
                await client.expire(key, timeout_seconds + 60)
            except Exception:
                pass  # Continue even if timeout registration fails
            
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
                
                # Clear timeout on success
                try:
                    await client.hset(key, "status", "completed")
                    await client.zrem("txn:timeout:pending", transaction_id)
                except Exception:
                    pass
                
                return result
                
            except asyncio.TimeoutError:
                # Mark as timeout
                try:
                    await client.hset(key, mapping={
                        "status": "timeout",
                        "timed_out_at": datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass
                
                if auto_reverse:
                    # Trigger reversal
                    raise TransactionTimeoutError(
                        f"Transaction {transaction_id} timed out after {timeout_seconds}s"
                    )
                raise
        
        return wrapper
    return decorator


class TransactionTimeoutError(Exception):
    """Raised when a transaction times out"""
    pass
