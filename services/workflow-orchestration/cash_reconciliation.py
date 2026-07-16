"""
End-of-Day Cash Reconciliation Workflow

Provides automated cash reconciliation for agents:
- Daily cash balance verification
- Float vs physical cash reconciliation
- Discrepancy detection and alerting
- Audit trail for compliance
- Automatic settlement triggers
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from temporalio import workflow, activity
from temporalio.common import RetryPolicy
import httpx

logger = logging.getLogger(__name__)

# Service URLs
LEDGER_SERVICE_URL = os.getenv("LEDGER_SERVICE_URL")
FLOAT_SERVICE_URL = os.getenv("FLOAT_SERVICE_URL")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL")
ANALYTICS_SERVICE_URL = os.getenv("ANALYTICS_SERVICE_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Optional imports
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

_db_pool = None


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


class ReconciliationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BALANCED = "balanced"
    DISCREPANCY = "discrepancy"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class DiscrepancyType(str, Enum):
    SHORTAGE = "shortage"      # Physical cash < expected
    OVERAGE = "overage"        # Physical cash > expected
    FLOAT_MISMATCH = "float_mismatch"
    TRANSACTION_MISSING = "transaction_missing"
    DUPLICATE_TRANSACTION = "duplicate_transaction"


@dataclass
class ReconciliationInput:
    agent_id: str
    reconciliation_date: str  # ISO format date
    reported_cash_balance: float
    reported_float_balance: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class TransactionSummary:
    total_cash_in: float = 0.0
    total_cash_out: float = 0.0
    total_commission: float = 0.0
    transaction_count: int = 0
    cash_in_count: int = 0
    cash_out_count: int = 0


@dataclass
class ReconciliationResult:
    agent_id: str
    reconciliation_date: str
    status: ReconciliationStatus
    expected_cash_balance: float
    reported_cash_balance: float
    expected_float_balance: float
    reported_float_balance: float
    discrepancy_amount: float
    discrepancy_type: Optional[DiscrepancyType]
    transaction_summary: TransactionSummary
    requires_action: bool
    action_items: List[str]
    reconciliation_id: str


# ============================================================================
# Reconciliation Activities
# ============================================================================

@activity.defn
async def get_agent_opening_balance(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get agent's opening balance for the day"""
    agent_id = data["agent_id"]
    recon_date = data["reconciliation_date"]
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Get previous day's closing balance
            prev_date = (datetime.fromisoformat(recon_date) - timedelta(days=1)).date()
            
            row = await conn.fetchrow("""
                SELECT closing_cash_balance, closing_float_balance
                FROM daily_reconciliation
                WHERE agent_id = $1 AND reconciliation_date = $2
                ORDER BY created_at DESC LIMIT 1
            """, agent_id, prev_date)
            
            if row:
                return {
                    "success": True,
                    "opening_cash_balance": float(row["closing_cash_balance"]),
                    "opening_float_balance": float(row["closing_float_balance"])
                }
            
            # No previous reconciliation, get from accounts
            account = await conn.fetchrow("""
                SELECT cash_balance, float_balance
                FROM agent_accounts
                WHERE agent_id = $1
            """, agent_id)
            
            if account:
                return {
                    "success": True,
                    "opening_cash_balance": float(account["cash_balance"]),
                    "opening_float_balance": float(account["float_balance"])
                }
            
            return {
                "success": True,
                "opening_cash_balance": 0.0,
                "opening_float_balance": 0.0
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to get opening balance: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def get_daily_transactions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get all transactions for the day"""
    agent_id = data["agent_id"]
    recon_date = data["reconciliation_date"]
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Parse date
            target_date = datetime.fromisoformat(recon_date).date()
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())
            
            # Get cash-in transactions
            cash_in = await conn.fetch("""
                SELECT transaction_id, amount, commission, created_at
                FROM transactions
                WHERE agent_id = $1 
                AND transaction_type = 'cash_in'
                AND created_at BETWEEN $2 AND $3
                AND status = 'completed'
            """, agent_id, start_time, end_time)
            
            # Get cash-out transactions
            cash_out = await conn.fetch("""
                SELECT transaction_id, amount, commission, created_at
                FROM transactions
                WHERE agent_id = $1 
                AND transaction_type = 'cash_out'
                AND created_at BETWEEN $2 AND $3
                AND status = 'completed'
            """, agent_id, start_time, end_time)
            
            # Calculate totals
            total_cash_in = sum(float(t["amount"]) for t in cash_in)
            total_cash_out = sum(float(t["amount"]) for t in cash_out)
            total_commission = sum(float(t["commission"] or 0) for t in cash_in) + \
                              sum(float(t["commission"] or 0) for t in cash_out)
            
            return {
                "success": True,
                "total_cash_in": total_cash_in,
                "total_cash_out": total_cash_out,
                "total_commission": total_commission,
                "cash_in_count": len(cash_in),
                "cash_out_count": len(cash_out),
                "transaction_count": len(cash_in) + len(cash_out),
                "transactions": {
                    "cash_in": [dict(t) for t in cash_in],
                    "cash_out": [dict(t) for t in cash_out]
                }
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to get daily transactions: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def get_ledger_balance(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get agent's balance from TigerBeetle ledger"""
    agent_id = data["agent_id"]
    
    if not LEDGER_SERVICE_URL:
        activity.logger.warning("LEDGER_SERVICE_URL not configured")
        return {"success": False, "error": "Ledger service not configured"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{LEDGER_SERVICE_URL}/api/v1/accounts/{agent_id}/balance"
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "ledger_balance": result.get("balance", 0),
                "available_balance": result.get("available_balance", 0),
                "pending_debits": result.get("pending_debits", 0),
                "pending_credits": result.get("pending_credits", 0)
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to get ledger balance: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def calculate_expected_balances(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate expected cash and float balances"""
    opening_cash = data["opening_cash_balance"]
    opening_float = data["opening_float_balance"]
    total_cash_in = data["total_cash_in"]
    total_cash_out = data["total_cash_out"]
    total_commission = data["total_commission"]
    
    # Cash balance calculation:
    # Cash-in: Agent receives physical cash, gives float
    # Cash-out: Agent gives physical cash, receives float
    expected_cash = opening_cash + total_cash_in - total_cash_out
    
    # Float balance calculation:
    # Cash-in: Float decreases (given to customer)
    # Cash-out: Float increases (received from customer)
    # Commission: Float increases
    expected_float = opening_float - total_cash_in + total_cash_out + total_commission
    
    return {
        "success": True,
        "expected_cash_balance": expected_cash,
        "expected_float_balance": expected_float,
        "calculation": {
            "opening_cash": opening_cash,
            "opening_float": opening_float,
            "cash_in_effect": total_cash_in,
            "cash_out_effect": total_cash_out,
            "commission_effect": total_commission
        }
    }


@activity.defn
async def detect_discrepancies(data: Dict[str, Any]) -> Dict[str, Any]:
    """Detect discrepancies between expected and reported balances"""
    expected_cash = data["expected_cash_balance"]
    reported_cash = data["reported_cash_balance"]
    expected_float = data["expected_float_balance"]
    reported_float = data.get("reported_float_balance", expected_float)
    
    # Tolerance for rounding errors (0.01 currency units)
    tolerance = 0.01
    
    cash_diff = reported_cash - expected_cash
    float_diff = reported_float - expected_float
    
    discrepancies = []
    
    if abs(cash_diff) > tolerance:
        if cash_diff < 0:
            discrepancies.append({
                "type": DiscrepancyType.SHORTAGE.value,
                "amount": abs(cash_diff),
                "description": f"Cash shortage of {abs(cash_diff):.2f}"
            })
        else:
            discrepancies.append({
                "type": DiscrepancyType.OVERAGE.value,
                "amount": cash_diff,
                "description": f"Cash overage of {cash_diff:.2f}"
            })
    
    if abs(float_diff) > tolerance:
        discrepancies.append({
            "type": DiscrepancyType.FLOAT_MISMATCH.value,
            "amount": abs(float_diff),
            "description": f"Float mismatch of {abs(float_diff):.2f}"
        })
    
    return {
        "success": True,
        "has_discrepancy": len(discrepancies) > 0,
        "discrepancies": discrepancies,
        "cash_difference": cash_diff,
        "float_difference": float_diff,
        "total_discrepancy": abs(cash_diff) + abs(float_diff)
    }


@activity.defn
async def save_reconciliation_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save reconciliation record to database"""
    import uuid
    
    reconciliation_id = str(uuid.uuid4())
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO daily_reconciliation (
                    reconciliation_id, agent_id, reconciliation_date,
                    opening_cash_balance, opening_float_balance,
                    total_cash_in, total_cash_out, total_commission,
                    expected_cash_balance, reported_cash_balance,
                    expected_float_balance, reported_float_balance,
                    closing_cash_balance, closing_float_balance,
                    discrepancy_amount, discrepancy_type, status,
                    transaction_count, notes, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, NOW()
                )
            """,
                reconciliation_id,
                data["agent_id"],
                datetime.fromisoformat(data["reconciliation_date"]).date(),
                data["opening_cash_balance"],
                data["opening_float_balance"],
                data["total_cash_in"],
                data["total_cash_out"],
                data["total_commission"],
                data["expected_cash_balance"],
                data["reported_cash_balance"],
                data["expected_float_balance"],
                data["reported_float_balance"],
                data["reported_cash_balance"],  # closing = reported
                data["reported_float_balance"],
                data["discrepancy_amount"],
                data.get("discrepancy_type"),
                data["status"],
                data["transaction_count"],
                data.get("notes")
            )
            
            activity.logger.info(
                f"Saved reconciliation record: {reconciliation_id}"
            )
            
            return {
                "success": True,
                "reconciliation_id": reconciliation_id
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to save reconciliation: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def send_reconciliation_alert(data: Dict[str, Any]) -> Dict[str, Any]:
    """Send alert for reconciliation discrepancies"""
    agent_id = data["agent_id"]
    discrepancy_amount = data["discrepancy_amount"]
    discrepancy_type = data.get("discrepancy_type")
    reconciliation_date = data["reconciliation_date"]
    
    if not NOTIFICATION_SERVICE_URL:
        activity.logger.warning("NOTIFICATION_SERVICE_URL not configured")
        return {"success": True, "skipped": True}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Alert agent
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/api/v1/notify",
                json={
                    "recipient_id": agent_id,
                    "recipient_type": "agent",
                    "template": "reconciliation_discrepancy",
                    "data": {
                        "date": reconciliation_date,
                        "discrepancy_amount": discrepancy_amount,
                        "discrepancy_type": discrepancy_type
                    },
                    "channels": ["sms", "push"],
                    "priority": "high"
                }
            )
            
            # Alert supervisor if significant discrepancy
            if discrepancy_amount > 10000:  # Threshold for escalation
                await client.post(
                    f"{NOTIFICATION_SERVICE_URL}/api/v1/notify",
                    json={
                        "recipient_type": "supervisor",
                        "agent_id": agent_id,
                        "template": "reconciliation_escalation",
                        "data": {
                            "agent_id": agent_id,
                            "date": reconciliation_date,
                            "discrepancy_amount": discrepancy_amount,
                            "discrepancy_type": discrepancy_type
                        },
                        "channels": ["email", "sms"],
                        "priority": "urgent"
                    }
                )
            
            return {"success": True, "notified": True}
            
    except Exception as e:
        activity.logger.error(f"Failed to send reconciliation alert: {e}")
        return {"success": False, "error": str(e)}


@activity.defn
async def record_reconciliation_analytics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Record reconciliation data for analytics"""
    if not ANALYTICS_SERVICE_URL:
        return {"success": True, "skipped": True}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{ANALYTICS_SERVICE_URL}/api/v1/events",
                json={
                    "event_type": "agent_reconciliation",
                    "agent_id": data["agent_id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {
                        "reconciliation_date": data["reconciliation_date"],
                        "status": data["status"],
                        "discrepancy_amount": data["discrepancy_amount"],
                        "transaction_count": data["transaction_count"],
                        "total_cash_in": data["total_cash_in"],
                        "total_cash_out": data["total_cash_out"]
                    }
                }
            )
            
            return {"success": True, "recorded": True}
            
    except Exception as e:
        activity.logger.error(f"Failed to record analytics: {e}")
        return {"success": True, "recorded": False}


# ============================================================================
# Reconciliation Workflow
# ============================================================================

@workflow.defn
class DailyCashReconciliationWorkflow:
    """
    End-of-day cash reconciliation workflow
    
    Steps:
    1. Get opening balance
    2. Get daily transactions
    3. Get ledger balance
    4. Calculate expected balances
    5. Detect discrepancies
    6. Save reconciliation record
    7. Send alerts if needed
    8. Record analytics
    """
    
    @workflow.run
    async def run(self, input: ReconciliationInput) -> Dict[str, Any]:
        """Execute reconciliation workflow"""
        
        # Step 1: Get opening balance
        opening = await workflow.execute_activity(
            get_agent_opening_balance,
            {
                "agent_id": input.agent_id,
                "reconciliation_date": input.reconciliation_date
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        if not opening["success"]:
            return {
                "status": "failed",
                "reason": f"Failed to get opening balance: {opening.get('error')}"
            }
        
        # Step 2: Get daily transactions
        transactions = await workflow.execute_activity(
            get_daily_transactions,
            {
                "agent_id": input.agent_id,
                "reconciliation_date": input.reconciliation_date
            },
            start_to_close_timeout=timedelta(seconds=60)
        )
        
        if not transactions["success"]:
            return {
                "status": "failed",
                "reason": f"Failed to get transactions: {transactions.get('error')}"
            }
        
        # Step 3: Get ledger balance (optional verification)
        ledger = await workflow.execute_activity(
            get_ledger_balance,
            {"agent_id": input.agent_id},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 4: Calculate expected balances
        expected = await workflow.execute_activity(
            calculate_expected_balances,
            {
                "opening_cash_balance": opening["opening_cash_balance"],
                "opening_float_balance": opening["opening_float_balance"],
                "total_cash_in": transactions["total_cash_in"],
                "total_cash_out": transactions["total_cash_out"],
                "total_commission": transactions["total_commission"]
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 5: Detect discrepancies
        reported_float = input.reported_float_balance or expected["expected_float_balance"]
        
        discrepancy = await workflow.execute_activity(
            detect_discrepancies,
            {
                "expected_cash_balance": expected["expected_cash_balance"],
                "reported_cash_balance": input.reported_cash_balance,
                "expected_float_balance": expected["expected_float_balance"],
                "reported_float_balance": reported_float
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Determine status
        if discrepancy["has_discrepancy"]:
            status = ReconciliationStatus.DISCREPANCY.value
            discrepancy_type = discrepancy["discrepancies"][0]["type"] if discrepancy["discrepancies"] else None
        else:
            status = ReconciliationStatus.BALANCED.value
            discrepancy_type = None
        
        # Step 6: Save reconciliation record
        save_result = await workflow.execute_activity(
            save_reconciliation_record,
            {
                "agent_id": input.agent_id,
                "reconciliation_date": input.reconciliation_date,
                "opening_cash_balance": opening["opening_cash_balance"],
                "opening_float_balance": opening["opening_float_balance"],
                "total_cash_in": transactions["total_cash_in"],
                "total_cash_out": transactions["total_cash_out"],
                "total_commission": transactions["total_commission"],
                "expected_cash_balance": expected["expected_cash_balance"],
                "reported_cash_balance": input.reported_cash_balance,
                "expected_float_balance": expected["expected_float_balance"],
                "reported_float_balance": reported_float,
                "discrepancy_amount": discrepancy["total_discrepancy"],
                "discrepancy_type": discrepancy_type,
                "status": status,
                "transaction_count": transactions["transaction_count"],
                "notes": input.notes
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 7: Send alerts if discrepancy
        if discrepancy["has_discrepancy"]:
            await workflow.execute_activity(
                send_reconciliation_alert,
                {
                    "agent_id": input.agent_id,
                    "reconciliation_date": input.reconciliation_date,
                    "discrepancy_amount": discrepancy["total_discrepancy"],
                    "discrepancy_type": discrepancy_type
                },
                start_to_close_timeout=timedelta(seconds=30)
            )
        
        # Step 8: Record analytics
        await workflow.execute_activity(
            record_reconciliation_analytics,
            {
                "agent_id": input.agent_id,
                "reconciliation_date": input.reconciliation_date,
                "status": status,
                "discrepancy_amount": discrepancy["total_discrepancy"],
                "transaction_count": transactions["transaction_count"],
                "total_cash_in": transactions["total_cash_in"],
                "total_cash_out": transactions["total_cash_out"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Build action items
        action_items = []
        if discrepancy["has_discrepancy"]:
            if discrepancy["cash_difference"] < 0:
                action_items.append(
                    f"Investigate cash shortage of {abs(discrepancy['cash_difference']):.2f}"
                )
            elif discrepancy["cash_difference"] > 0:
                action_items.append(
                    f"Verify cash overage of {discrepancy['cash_difference']:.2f}"
                )
            if abs(discrepancy["float_difference"]) > 0.01:
                action_items.append(
                    f"Reconcile float difference of {abs(discrepancy['float_difference']):.2f}"
                )
        
        return {
            "status": status,
            "reconciliation_id": save_result.get("reconciliation_id"),
            "agent_id": input.agent_id,
            "reconciliation_date": input.reconciliation_date,
            "expected_cash_balance": expected["expected_cash_balance"],
            "reported_cash_balance": input.reported_cash_balance,
            "expected_float_balance": expected["expected_float_balance"],
            "reported_float_balance": reported_float,
            "discrepancy_amount": discrepancy["total_discrepancy"],
            "discrepancy_type": discrepancy_type,
            "transaction_summary": {
                "total_cash_in": transactions["total_cash_in"],
                "total_cash_out": transactions["total_cash_out"],
                "total_commission": transactions["total_commission"],
                "transaction_count": transactions["transaction_count"]
            },
            "requires_action": discrepancy["has_discrepancy"],
            "action_items": action_items,
            "ledger_balance": ledger.get("ledger_balance") if ledger.get("success") else None
        }


# Batch reconciliation for all agents
@workflow.defn
class BatchReconciliationWorkflow:
    """Run reconciliation for all active agents"""
    
    @workflow.run
    async def run(self, reconciliation_date: str) -> Dict[str, Any]:
        """Execute batch reconciliation"""
        
        # Get all active agents
        agents = await workflow.execute_activity(
            get_active_agents,
            {},
            start_to_close_timeout=timedelta(seconds=60)
        )
        
        results = {
            "date": reconciliation_date,
            "total_agents": len(agents.get("agents", [])),
            "balanced": 0,
            "discrepancies": 0,
            "failed": 0,
            "details": []
        }
        
        for agent in agents.get("agents", []):
            try:
                # Start child workflow for each agent
                result = await workflow.execute_child_workflow(
                    DailyCashReconciliationWorkflow.run,
                    ReconciliationInput(
                        agent_id=agent["agent_id"],
                        reconciliation_date=reconciliation_date,
                        reported_cash_balance=agent.get("reported_cash", 0)
                    ),
                    id=f"recon-{agent['agent_id']}-{reconciliation_date}"
                )
                
                if result["status"] == ReconciliationStatus.BALANCED.value:
                    results["balanced"] += 1
                elif result["status"] == ReconciliationStatus.DISCREPANCY.value:
                    results["discrepancies"] += 1
                else:
                    results["failed"] += 1
                
                results["details"].append({
                    "agent_id": agent["agent_id"],
                    "status": result["status"],
                    "discrepancy_amount": result.get("discrepancy_amount", 0)
                })
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "agent_id": agent["agent_id"],
                    "status": "error",
                    "error": str(e)
                })
        
        return results


@activity.defn
async def get_active_agents(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get list of active agents for reconciliation"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT agent_id, cash_balance as reported_cash
                FROM agent_accounts
                WHERE status = 'active'
            """)
            
            return {
                "success": True,
                "agents": [dict(r) for r in rows]
            }
            
    except Exception as e:
        activity.logger.error(f"Failed to get active agents: {e}")
        return {"success": False, "agents": [], "error": str(e)}
