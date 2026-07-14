"""
Compensation Activities for Transaction Rollback

Provides saga pattern compensation for failed transactions:
- Ledger reversal (TigerBeetle)
- Float restoration
- Commission reversal
- Notification of failed transactions
- Audit trail for compensations
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from temporalio import activity
import httpx

logger = logging.getLogger(__name__)

# Service URLs from environment
LEDGER_SERVICE_URL = os.getenv("LEDGER_SERVICE_URL")
FLOAT_SERVICE_URL = os.getenv("FLOAT_SERVICE_URL")
COMMISSION_SERVICE_URL = os.getenv("COMMISSION_SERVICE_URL")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL")
ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Optional imports
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None

_db_pool = None


async def get_db_pool():
    """Get or create database connection pool"""
    global _db_pool
    if _db_pool is None:
        if not HAS_ASYNCPG:
            raise ValueError("asyncpg not installed")
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL not set")
        _db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    return _db_pool


@activity.defn
async def reverse_ledger_transaction(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reverse a ledger transaction in TigerBeetle
    
    Creates a compensating transfer that reverses the original transaction.
    Uses linked transfers to ensure atomicity.
    """
    original_transfer_id = data.get("transfer_id")
    original_debit_account = data.get("debit_account")
    original_credit_account = data.get("credit_account")
    amount = data.get("amount")
    reason = data.get("reason", "transaction_compensation")
    
    if not LEDGER_SERVICE_URL:
        activity.logger.error("LEDGER_SERVICE_URL not configured")
        return {
            "success": False,
            "error": "Ledger service not configured",
            "requires_manual_intervention": True
        }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create reversal transfer (swap debit and credit)
            response = await client.post(
                f"{LEDGER_SERVICE_URL}/api/v1/transfers/reverse",
                json={
                    "original_transfer_id": original_transfer_id,
                    "debit_account_id": original_credit_account,  # Reversed
                    "credit_account_id": original_debit_account,  # Reversed
                    "amount": amount,
                    "code": 9999,  # Reversal code
                    "metadata": {
                        "type": "compensation",
                        "reason": reason,
                        "original_transfer_id": original_transfer_id,
                        "compensated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            
            activity.logger.info(
                f"Reversed ledger transaction {original_transfer_id}: "
                f"reversal_id={result.get('transfer_id')}"
            )
            
            return {
                "success": True,
                "reversal_transfer_id": result.get("transfer_id"),
                "original_transfer_id": original_transfer_id,
                "amount": amount,
                "compensated_at": datetime.utcnow().isoformat()
            }
            
    except httpx.HTTPStatusError as e:
        activity.logger.error(f"Ledger reversal HTTP error: {e}")
        return {
            "success": False,
            "error": str(e),
            "requires_manual_intervention": True,
            "original_transfer_id": original_transfer_id
        }
    except Exception as e:
        activity.logger.error(f"Ledger reversal failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "requires_manual_intervention": True,
            "original_transfer_id": original_transfer_id
        }


@activity.defn
async def restore_agent_float(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Restore agent float after failed cash-in transaction
    
    When a cash-in fails after float was deducted, this restores the float.
    """
    agent_id = data.get("agent_id")
    amount = data.get("amount")
    transaction_id = data.get("transaction_id")
    reason = data.get("reason", "cash_in_compensation")
    
    if not FLOAT_SERVICE_URL:
        activity.logger.error("FLOAT_SERVICE_URL not configured")
        return {
            "success": False,
            "error": "Float service not configured",
            "requires_manual_intervention": True
        }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FLOAT_SERVICE_URL}/api/v1/float/restore",
                json={
                    "agent_id": agent_id,
                    "amount": amount,
                    "transaction_id": transaction_id,
                    "reason": reason,
                    "type": "compensation"
                }
            )
            response.raise_for_status()
            result = response.json()
            
            activity.logger.info(
                f"Restored float for agent {agent_id}: amount={amount}"
            )
            
            return {
                "success": True,
                "agent_id": agent_id,
                "amount_restored": amount,
                "new_balance": result.get("balance"),
                "compensated_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        activity.logger.error(f"Float restoration failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "requires_manual_intervention": True,
            "agent_id": agent_id,
            "amount": amount
        }


@activity.defn
async def restore_customer_balance(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Restore customer balance after failed cash-out transaction
    
    When a cash-out fails after balance was deducted, this restores the balance.
    """
    customer_id = data.get("customer_id")
    amount = data.get("amount")
    transaction_id = data.get("transaction_id")
    reason = data.get("reason", "cash_out_compensation")
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Restore balance
                await conn.execute("""
                    UPDATE accounts 
                    SET balance = balance + $1,
                        available_balance = available_balance + $1,
                        updated_at = NOW()
                    WHERE customer_id = $2 AND account_type = 'primary'
                """, amount, customer_id)
                
                # Record compensation
                await conn.execute("""
                    INSERT INTO transaction_compensations
                    (transaction_id, customer_id, amount, type, reason, created_at)
                    VALUES ($1, $2, $3, 'balance_restore', $4, NOW())
                """, transaction_id, customer_id, amount, reason)
                
                # Get new balance
                row = await conn.fetchrow("""
                    SELECT balance, available_balance FROM accounts
                    WHERE customer_id = $1 AND account_type = 'primary'
                """, customer_id)
                
                activity.logger.info(
                    f"Restored balance for customer {customer_id}: amount={amount}"
                )
                
                return {
                    "success": True,
                    "customer_id": customer_id,
                    "amount_restored": amount,
                    "new_balance": float(row["balance"]) if row else None,
                    "compensated_at": datetime.utcnow().isoformat()
                }
                
    except Exception as e:
        activity.logger.error(f"Balance restoration failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "requires_manual_intervention": True,
            "customer_id": customer_id,
            "amount": amount
        }


@activity.defn
async def reverse_commission(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reverse commission credited to agent after failed transaction
    """
    agent_id = data.get("agent_id")
    commission_id = data.get("commission_id")
    amount = data.get("amount")
    transaction_id = data.get("transaction_id")
    
    if not COMMISSION_SERVICE_URL:
        activity.logger.warning("COMMISSION_SERVICE_URL not configured, skipping")
        return {
            "success": True,
            "skipped": True,
            "reason": "Commission service not configured"
        }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{COMMISSION_SERVICE_URL}/api/v1/commissions/reverse",
                json={
                    "commission_id": commission_id,
                    "agent_id": agent_id,
                    "amount": amount,
                    "transaction_id": transaction_id,
                    "reason": "transaction_compensation"
                }
            )
            response.raise_for_status()
            result = response.json()
            
            activity.logger.info(
                f"Reversed commission {commission_id} for agent {agent_id}"
            )
            
            return {
                "success": True,
                "commission_id": commission_id,
                "amount_reversed": amount,
                "compensated_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        activity.logger.error(f"Commission reversal failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "requires_manual_intervention": True,
            "commission_id": commission_id,
            "amount": amount
        }


@activity.defn
async def send_compensation_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send notification about transaction compensation/reversal
    """
    customer_id = data.get("customer_id")
    agent_id = data.get("agent_id")
    transaction_id = data.get("transaction_id")
    transaction_type = data.get("transaction_type")
    amount = data.get("amount")
    reason = data.get("reason")
    
    if not NOTIFICATION_SERVICE_URL:
        activity.logger.warning("NOTIFICATION_SERVICE_URL not configured")
        return {"success": True, "skipped": True}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Notify customer
            if customer_id:
                await client.post(
                    f"{NOTIFICATION_SERVICE_URL}/api/v1/notify",
                    json={
                        "recipient_id": customer_id,
                        "recipient_type": "customer",
                        "template": "transaction_reversed",
                        "data": {
                            "transaction_id": transaction_id,
                            "transaction_type": transaction_type,
                            "amount": amount,
                            "reason": reason
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
                        "template": "transaction_reversed",
                        "data": {
                            "transaction_id": transaction_id,
                            "transaction_type": transaction_type,
                            "amount": amount,
                            "reason": reason
                        },
                        "channels": ["sms", "push"]
                    }
                )
            
            return {"success": True, "notified": True}
            
    except Exception as e:
        activity.logger.error(f"Compensation notification failed: {e}")
        return {"success": True, "notified": False, "error": str(e)}


@activity.defn
async def record_compensation_audit(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Record compensation in audit trail for compliance
    """
    transaction_id = data.get("transaction_id")
    compensation_type = data.get("compensation_type")
    original_amount = data.get("original_amount")
    compensated_amount = data.get("compensated_amount")
    reason = data.get("reason")
    steps_completed = data.get("steps_completed", [])
    steps_failed = data.get("steps_failed", [])
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO compensation_audit_log
                (transaction_id, compensation_type, original_amount, 
                 compensated_amount, reason, steps_completed, steps_failed,
                 created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, transaction_id, compensation_type, original_amount,
                compensated_amount, reason, steps_completed, steps_failed)
            
            activity.logger.info(
                f"Recorded compensation audit for transaction {transaction_id}"
            )
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "audit_recorded": True
            }
            
    except Exception as e:
        activity.logger.error(f"Compensation audit recording failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "transaction_id": transaction_id
        }


@activity.defn
async def release_transaction_lock(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Release distributed lock for transaction
    """
    lock_key = data.get("lock_key")
    transaction_id = data.get("transaction_id")
    
    try:
        import redis.asyncio as redis
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return {"success": True, "skipped": True, "reason": "Redis not configured"}
        
        client = redis.from_url(redis_url)
        await client.delete(f"txn:lock:{lock_key}")
        await client.close()
        
        activity.logger.info(f"Released lock for transaction {transaction_id}")
        
        return {
            "success": True,
            "lock_key": lock_key,
            "released": True
        }
        
    except Exception as e:
        activity.logger.error(f"Lock release failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "lock_key": lock_key
        }


# Compensation workflow helper
async def execute_cash_in_compensation(
    workflow,
    transaction_id: str,
    agent_id: str,
    customer_id: str,
    amount: float,
    ledger_transfer_id: Optional[str],
    commission_id: Optional[str],
    commission_amount: Optional[float],
    reason: str
) -> Dict[str, Any]:
    """
    Execute full compensation for failed cash-in transaction
    
    Steps:
    1. Reverse ledger transaction (if exists)
    2. Restore agent float
    3. Reverse commission (if credited)
    4. Send notifications
    5. Record audit trail
    6. Release locks
    """
    from temporalio import workflow
    from datetime import timedelta
    
    compensation_results = {
        "transaction_id": transaction_id,
        "steps_completed": [],
        "steps_failed": [],
        "requires_manual_intervention": False
    }
    
    # Step 1: Reverse ledger transaction
    if ledger_transfer_id:
        result = await workflow.execute_activity(
            reverse_ledger_transaction,
            {
                "transfer_id": ledger_transfer_id,
                "debit_account": agent_id,
                "credit_account": customer_id,
                "amount": amount,
                "reason": reason
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        if result["success"]:
            compensation_results["steps_completed"].append("ledger_reversal")
        else:
            compensation_results["steps_failed"].append("ledger_reversal")
            compensation_results["requires_manual_intervention"] = True
    
    # Step 2: Restore agent float
    result = await workflow.execute_activity(
        restore_agent_float,
        {
            "agent_id": agent_id,
            "amount": amount,
            "transaction_id": transaction_id,
            "reason": reason
        },
        start_to_close_timeout=timedelta(seconds=30)
    )
    if result["success"]:
        compensation_results["steps_completed"].append("float_restoration")
    else:
        compensation_results["steps_failed"].append("float_restoration")
        compensation_results["requires_manual_intervention"] = True
    
    # Step 3: Reverse commission
    if commission_id and commission_amount:
        result = await workflow.execute_activity(
            reverse_commission,
            {
                "agent_id": agent_id,
                "commission_id": commission_id,
                "amount": commission_amount,
                "transaction_id": transaction_id
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        if result["success"]:
            compensation_results["steps_completed"].append("commission_reversal")
        else:
            compensation_results["steps_failed"].append("commission_reversal")
    
    # Step 4: Send notifications
    await workflow.execute_activity(
        send_compensation_notification,
        {
            "customer_id": customer_id,
            "agent_id": agent_id,
            "transaction_id": transaction_id,
            "transaction_type": "cash_in",
            "amount": amount,
            "reason": reason
        },
        start_to_close_timeout=timedelta(seconds=30)
    )
    compensation_results["steps_completed"].append("notification")
    
    # Step 5: Record audit
    await workflow.execute_activity(
        record_compensation_audit,
        {
            "transaction_id": transaction_id,
            "compensation_type": "cash_in_reversal",
            "original_amount": amount,
            "compensated_amount": amount,
            "reason": reason,
            "steps_completed": compensation_results["steps_completed"],
            "steps_failed": compensation_results["steps_failed"]
        },
        start_to_close_timeout=timedelta(seconds=10)
    )
    
    # Step 6: Release lock
    await workflow.execute_activity(
        release_transaction_lock,
        {
            "lock_key": f"{agent_id}:{customer_id}",
            "transaction_id": transaction_id
        },
        start_to_close_timeout=timedelta(seconds=5)
    )
    
    return compensation_results


async def execute_cash_out_compensation(
    workflow,
    transaction_id: str,
    agent_id: str,
    customer_id: str,
    amount: float,
    ledger_transfer_id: Optional[str],
    commission_id: Optional[str],
    commission_amount: Optional[float],
    reason: str
) -> Dict[str, Any]:
    """
    Execute full compensation for failed cash-out transaction
    
    Steps:
    1. Reverse ledger transaction (if exists)
    2. Restore customer balance
    3. Reverse commission (if credited)
    4. Send notifications
    5. Record audit trail
    6. Release locks
    """
    from temporalio import workflow
    from datetime import timedelta
    
    compensation_results = {
        "transaction_id": transaction_id,
        "steps_completed": [],
        "steps_failed": [],
        "requires_manual_intervention": False
    }
    
    # Step 1: Reverse ledger transaction
    if ledger_transfer_id:
        result = await workflow.execute_activity(
            reverse_ledger_transaction,
            {
                "transfer_id": ledger_transfer_id,
                "debit_account": customer_id,
                "credit_account": agent_id,
                "amount": amount,
                "reason": reason
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        if result["success"]:
            compensation_results["steps_completed"].append("ledger_reversal")
        else:
            compensation_results["steps_failed"].append("ledger_reversal")
            compensation_results["requires_manual_intervention"] = True
    
    # Step 2: Restore customer balance
    result = await workflow.execute_activity(
        restore_customer_balance,
        {
            "customer_id": customer_id,
            "amount": amount,
            "transaction_id": transaction_id,
            "reason": reason
        },
        start_to_close_timeout=timedelta(seconds=30)
    )
    if result["success"]:
        compensation_results["steps_completed"].append("balance_restoration")
    else:
        compensation_results["steps_failed"].append("balance_restoration")
        compensation_results["requires_manual_intervention"] = True
    
    # Step 3: Reverse commission
    if commission_id and commission_amount:
        result = await workflow.execute_activity(
            reverse_commission,
            {
                "agent_id": agent_id,
                "commission_id": commission_id,
                "amount": commission_amount,
                "transaction_id": transaction_id
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        if result["success"]:
            compensation_results["steps_completed"].append("commission_reversal")
        else:
            compensation_results["steps_failed"].append("commission_reversal")
    
    # Step 4: Send notifications
    await workflow.execute_activity(
        send_compensation_notification,
        {
            "customer_id": customer_id,
            "agent_id": agent_id,
            "transaction_id": transaction_id,
            "transaction_type": "cash_out",
            "amount": amount,
            "reason": reason
        },
        start_to_close_timeout=timedelta(seconds=30)
    )
    compensation_results["steps_completed"].append("notification")
    
    # Step 5: Record audit
    await workflow.execute_activity(
        record_compensation_audit,
        {
            "transaction_id": transaction_id,
            "compensation_type": "cash_out_reversal",
            "original_amount": amount,
            "compensated_amount": amount,
            "reason": reason,
            "steps_completed": compensation_results["steps_completed"],
            "steps_failed": compensation_results["steps_failed"]
        },
        start_to_close_timeout=timedelta(seconds=10)
    )
    
    # Step 6: Release lock
    await workflow.execute_activity(
        release_transaction_lock,
        {
            "lock_key": f"{agent_id}:{customer_id}",
            "transaction_id": transaction_id
        },
        start_to_close_timeout=timedelta(seconds=5)
    )
    
    return compensation_results
