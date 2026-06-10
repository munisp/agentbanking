import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Remittance Platform - Settlement Service
Handles commission settlement processing with TigerBeetle ledger integration
Processes commission payouts, settlement batches, and approval workflows
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

import asyncpg
import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Header, status
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("settlement-service")
app.include_router(metrics_router)

from pydantic import BaseModel, validator, Field
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Settlement Service",
    description="Commission settlement processing with TigerBeetle integration",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://banking_user:banking_pass@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
COMMISSION_SERVICE_URL = os.getenv("COMMISSION_SERVICE_URL", "http://localhost:8010")
TIGERBEETLE_SERVICE_URL = os.getenv("TIGERBEETLE_SERVICE_URL", "http://localhost:8028")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8030")
FEE_SCHEDULE_SERVICE_URL = os.getenv("FEE_SCHEDULE_SERVICE_URL", "http://localhost:8106")

# Database and Redis connections
db_pool = None
redis_client = None
http_client = None

# =====================================================
# ENUMS AND CONSTANTS
# =====================================================

class SettlementStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SettlementFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    MANUAL = "manual"

class PayoutMethod(str, Enum):
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    WALLET = "wallet"
    CASH = "cash"
    CHECK = "check"

class SettlementItemStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

# =====================================================
# DATA MODELS
# =====================================================

class SettlementRuleCreate(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    frequency: SettlementFrequency
    settlement_day: Optional[int] = Field(None, ge=1, le=31)  # Day of month for monthly
    settlement_weekday: Optional[int] = Field(None, ge=0, le=6)  # 0=Monday for weekly
    min_settlement_amount: Decimal = Field(Decimal("10.00"), ge=0)
    auto_approve: bool = False
    auto_approve_threshold: Optional[Decimal] = Field(None, ge=0)
    payout_method: PayoutMethod = PayoutMethod.BANK_TRANSFER
    is_active: bool = True
    agent_tier: Optional[str] = None
    territory_id: Optional[str] = None

class SettlementRuleResponse(BaseModel):
    id: str
    rule_name: str
    description: Optional[str]
    frequency: str
    settlement_day: Optional[int]
    settlement_weekday: Optional[int]
    min_settlement_amount: Decimal
    auto_approve: bool
    auto_approve_threshold: Optional[Decimal]
    payout_method: str
    is_active: bool
    agent_tier: Optional[str]
    territory_id: Optional[str]
    created_at: datetime
    updated_at: datetime

class SettlementBatchCreate(BaseModel):
    batch_name: str
    settlement_period_start: date
    settlement_period_end: date
    settlement_rule_id: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    description: Optional[str] = None
    auto_process: bool = False

class SettlementBatchResponse(BaseModel):
    id: str
    batch_name: str
    batch_number: str
    settlement_period_start: date
    settlement_period_end: date
    settlement_rule_id: Optional[str]
    status: str
    total_agents: int
    total_amount: Decimal
    total_items: int
    completed_items: int
    failed_items: int
    created_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class SettlementItemResponse(BaseModel):
    id: str
    batch_id: str
    agent_id: str
    agent_name: Optional[str]
    gross_commission: Decimal
    deductions: Decimal
    net_amount: Decimal
    payout_method: str
    payout_details: Dict[str, Any]
    status: str
    tigerbeetle_transfer_id: Optional[str]
    error_message: Optional[str]
    retry_count: int
    processed_at: Optional[datetime]
    created_at: datetime

class SettlementApprovalRequest(BaseModel):
    approved: bool
    approver_id: str
    approval_notes: Optional[str] = None

class SettlementProcessRequest(BaseModel):
    force_reprocess: bool = False
    notify_agents: bool = True

class CommissionSummaryResponse(BaseModel):
    agent_id: str
    period_start: date
    period_end: date
    total_transactions: int
    gross_commission: Decimal
    hierarchy_commission: Decimal
    total_commission: Decimal
    previous_settlements: Decimal
    pending_amount: Decimal

# =====================================================
# DATABASE CONNECTION
# =====================================================

async def get_db_connection():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    return await db_pool.acquire()

async def release_db_connection(conn):
    """Release database connection back to pool"""
    await db_pool.release(conn)

async def get_redis_connection():
    """Get Redis connection"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL)
    return redis_client

async def get_http_client():
    """Get HTTP client for service calls"""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=30.0)
    return http_client

# =====================================================
# SETTLEMENT ENGINE
# =====================================================

class SettlementEngine:
    """Settlement processing engine with TigerBeetle integration"""
    
    def __init__(self, db_connection, redis_connection, http_client):
        self.db = db_connection
        self.redis = redis_connection
        self.http = http_client
    
    async def create_settlement_batch(self, batch_data: SettlementBatchCreate, created_by: str, idempotency_key: Optional[str] = None) -> str:
        """Create a new settlement batch with idempotency support."""
        if idempotency_key:
            try:
                acquired = await self.redis.set(f"settlement_idempotency:{idempotency_key}", "processing", nx=True, ex=86400)
                if not acquired:
                    cached_batch_id = await self.redis.get(f"settlement_idempotency:{idempotency_key}")
                    if cached_batch_id and cached_batch_id != "processing":
                        bid = cached_batch_id if isinstance(cached_batch_id, str) else cached_batch_id.decode()
                        existing = await self.db.fetchrow("SELECT id FROM settlement_batches WHERE id = $1", bid)
                        if existing:
                            logger.info(f"Idempotency hit for settlement key={idempotency_key}")
                            return bid
            except Exception as exc:
                logger.warning(f"Redis idempotency check failed: {exc}")

        batch_id = str(uuid.uuid4())
        batch_number = await self._generate_batch_number()
        
        # Get settlement rule if specified
        rule = None
        if batch_data.settlement_rule_id:
            rule = await self._get_settlement_rule(batch_data.settlement_rule_id)
        
        # Get agents to settle
        agent_ids = batch_data.agent_ids
        if not agent_ids:
            agent_ids = await self._get_all_active_agents()
        
        # Calculate commission summaries for each agent
        settlement_items = []
        total_amount = Decimal("0")
        
        for agent_id in agent_ids:
            summary = await self._get_agent_commission_summary(
                agent_id,
                batch_data.settlement_period_start,
                batch_data.settlement_period_end
            )
            
            # Check minimum settlement amount
            min_amount = rule['min_settlement_amount'] if rule else Decimal("10.00")
            if summary['pending_amount'] < min_amount:
                logger.info(f"Agent {agent_id} below minimum settlement amount: {summary['pending_amount']}")
                continue
            
            # Create settlement item
            item_id = str(uuid.uuid4())
            settlement_items.append({
                'id': item_id,
                'batch_id': batch_id,
                'agent_id': agent_id,
                'gross_commission': summary['total_commission'],
                'deductions': await self._calculate_deductions(agent_id, summary['total_commission']),
                'net_amount': summary['pending_amount'],
                'payout_method': rule['payout_method'] if rule else PayoutMethod.BANK_TRANSFER,
                'payout_details': await self._get_agent_payout_details(agent_id),
                'status': SettlementItemStatus.PENDING
            })
            total_amount += summary['pending_amount']
        
        # Insert batch into database
        await self.db.execute("""
            INSERT INTO settlement_batches (
                id, batch_name, batch_number, settlement_period_start, settlement_period_end,
                settlement_rule_id, status, total_agents, total_amount, total_items,
                completed_items, failed_items, created_by, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """, batch_id, batch_data.batch_name, batch_number, batch_data.settlement_period_start,
            batch_data.settlement_period_end, batch_data.settlement_rule_id, SettlementStatus.PENDING,
            len(settlement_items), total_amount, len(settlement_items), 0, 0, created_by,
            datetime.utcnow(), datetime.utcnow())
        
        # Insert settlement items
        for item in settlement_items:
            await self.db.execute("""
                INSERT INTO settlement_items (
                    id, batch_id, agent_id, gross_commission, deductions, net_amount,
                    payout_method, payout_details, status, retry_count, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, item['id'], item['batch_id'], item['agent_id'], item['gross_commission'],
                item['deductions'], item['net_amount'], item['payout_method'].value,
                json.dumps(item['payout_details']), item['status'].value, 0, datetime.utcnow())
        
        logger.info(f"Created settlement batch {batch_id} with {len(settlement_items)} items, total: {total_amount}")

        if idempotency_key:
            try:
                await self.redis.setex(
                    f"settlement_idempotency:{idempotency_key}",
                    86400,
                    batch_id,
                )
            except Exception:
                pass

        # Auto-process if requested
        if batch_data.auto_process and rule and rule['auto_approve']:
            if total_amount <= rule.get('auto_approve_threshold', Decimal("1000000")):
                await self._auto_approve_batch(batch_id, "system")
        
        return batch_id
    
    async def approve_settlement_batch(self, batch_id: str, approval: SettlementApprovalRequest) -> bool:
        """Approve or reject a settlement batch"""
        # Get batch
        batch = await self.db.fetchrow(
            "SELECT * FROM settlement_batches WHERE id = $1", batch_id
        )
        
        if not batch:
            raise HTTPException(status_code=404, detail="Settlement batch not found")
        
        if batch['status'] != SettlementStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"Batch is not pending (status: {batch['status']})")
        
        if approval.approved:
            # Approve batch
            await self.db.execute("""
                UPDATE settlement_batches
                SET status = $1, approved_by = $2, approved_at = $3, updated_at = $4
                WHERE id = $5
            """, SettlementStatus.APPROVED, approval.approver_id, datetime.utcnow(),
                datetime.utcnow(), batch_id)
            
            logger.info(f"Settlement batch {batch_id} approved by {approval.approver_id}")
            return True
        else:
            # Reject batch
            await self.db.execute("""
                UPDATE settlement_batches
                SET status = $1, updated_at = $2
                WHERE id = $3
            """, SettlementStatus.REJECTED, datetime.utcnow(), batch_id)
            
            logger.info(f"Settlement batch {batch_id} rejected by {approval.approver_id}")
            return False
    
    async def process_settlement_batch(self, batch_id: str, notify_agents: bool = True) -> Dict[str, Any]:
        """Process an approved settlement batch"""
        # Get batch
        batch = await self.db.fetchrow(
            "SELECT * FROM settlement_batches WHERE id = $1", batch_id
        )
        
        if not batch:
            raise HTTPException(status_code=404, detail="Settlement batch not found")
        
        if batch['status'] not in [SettlementStatus.APPROVED, SettlementStatus.FAILED]:
            raise HTTPException(
                status_code=400,
                detail=f"Batch must be approved before processing (status: {batch['status']})"
            )
        
        # Update batch status to processing
        await self.db.execute("""
            UPDATE settlement_batches
            SET status = $1, updated_at = $2
            WHERE id = $3
        """, SettlementStatus.PROCESSING, datetime.utcnow(), batch_id)
        
        # Get settlement items
        items = await self.db.fetch("""
            SELECT * FROM settlement_items
            WHERE batch_id = $1 AND status IN ($2, $3)
        """, batch_id, SettlementItemStatus.PENDING, SettlementItemStatus.FAILED)
        
        completed = 0
        failed = 0
        
        # Process each settlement item
        for item in items:
            try:
                # Process payout via TigerBeetle
                transfer_id = await self._process_payout_tigerbeetle(item)
                
                # Update item status
                await self.db.execute("""
                    UPDATE settlement_items
                    SET status = $1, tigerbeetle_transfer_id = $2, processed_at = $3
                    WHERE id = $4
                """, SettlementItemStatus.COMPLETED, transfer_id, datetime.utcnow(), item['id'])
                
                # Mark commissions as settled
                await self._mark_commissions_settled(
                    item['agent_id'],
                    batch['settlement_period_start'],
                    batch['settlement_period_end'],
                    batch_id
                )
                
                completed += 1
                logger.info(f"Processed settlement item {item['id']} for agent {item['agent_id']}")
                
                # Send notification
                if notify_agents:
                    await self._send_settlement_notification(item, transfer_id)
                
            except Exception as e:
                # Update item as failed
                await self.db.execute("""
                    UPDATE settlement_items
                    SET status = $1, error_message = $2, retry_count = retry_count + 1
                    WHERE id = $3
                """, SettlementItemStatus.FAILED, str(e), item['id'])
                
                failed += 1
                logger.error(f"Failed to process settlement item {item['id']}: {str(e)}")
        
        # Update batch status
        final_status = SettlementStatus.COMPLETED if failed == 0 else SettlementStatus.FAILED
        await self.db.execute("""
            UPDATE settlement_batches
            SET status = $1, completed_items = $2, failed_items = $3,
                processed_at = $4, updated_at = $5
            WHERE id = $6
        """, final_status, completed, failed, datetime.utcnow(), datetime.utcnow(), batch_id)
        
        logger.info(f"Processed settlement batch {batch_id}: {completed} completed, {failed} failed")
        
        return {
            'batch_id': batch_id,
            'status': final_status,
            'completed': completed,
            'failed': failed,
            'total': len(items)
        }
    
    async def retry_failed_settlements(self, batch_id: str, max_retries: int = 3) -> Dict[str, Any]:
        """Retry failed settlement items"""
        items = await self.db.fetch("""
            SELECT * FROM settlement_items
            WHERE batch_id = $1 AND status = $2 AND retry_count < $3
        """, batch_id, SettlementItemStatus.FAILED, max_retries)
        
        retried = 0
        succeeded = 0
        
        for item in items:
            try:
                # Mark as retrying
                await self.db.execute("""
                    UPDATE settlement_items
                    SET status = $1
                    WHERE id = $2
                """, SettlementItemStatus.RETRYING, item['id'])
                
                # Retry payout
                transfer_id = await self._process_payout_tigerbeetle(item)
                
                # Update as completed
                await self.db.execute("""
                    UPDATE settlement_items
                    SET status = $1, tigerbeetle_transfer_id = $2, processed_at = $3, error_message = NULL
                    WHERE id = $4
                """, SettlementItemStatus.COMPLETED, transfer_id, datetime.utcnow(), item['id'])
                
                succeeded += 1
                retried += 1
                
            except Exception as e:
                # Update retry count and error
                await self.db.execute("""
                    UPDATE settlement_items
                    SET status = $1, error_message = $2, retry_count = retry_count + 1
                    WHERE id = $3
                """, SettlementItemStatus.FAILED, str(e), item['id'])
                
                retried += 1
        
        return {
            'batch_id': batch_id,
            'retried': retried,
            'succeeded': succeeded,
            'failed': retried - succeeded
        }
    
    # =====================================================
    # HELPER METHODS
    # =====================================================
    
    async def _generate_batch_number(self) -> str:
        """Generate unique batch number"""
        today = datetime.utcnow().strftime("%Y%m%d")
        count = await self.db.fetchval("""
            SELECT COUNT(*) FROM settlement_batches
            WHERE batch_number LIKE $1
        """, f"STL-{today}-%")
        return f"STL-{today}-{count + 1:04d}"
    
    async def _get_settlement_rule(self, rule_id: str) -> Dict:
        """Get settlement rule"""
        rule = await self.db.fetchrow(
            "SELECT * FROM settlement_rules WHERE id = $1", rule_id
        )
        if not rule:
            raise HTTPException(status_code=404, detail="Settlement rule not found")
        return dict(rule)
    
    async def _get_all_active_agents(self) -> List[str]:
        """Get all active agent IDs"""
        rows = await self.db.fetch("""
            SELECT id FROM agents WHERE status = 'active'
        """)
        return [row['id'] for row in rows]
    
    async def _get_agent_commission_summary(
        self, agent_id: str, period_start: date, period_end: date
    ) -> Dict:
        """Get agent commission summary from commission service"""
        try:
            response = await self.http.get(
                f"{COMMISSION_SERVICE_URL}/commission/agent/{agent_id}/summary",
                params={
                    'period_start': period_start.isoformat(),
                    'period_end': period_end.isoformat()
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get commission summary for agent {agent_id}: {str(e)}")
            # Return default summary
            return {
                'agent_id': agent_id,
                'period_start': period_start,
                'period_end': period_end,
                'total_transactions': 0,
                'gross_commission': Decimal("0"),
                'hierarchy_commission': Decimal("0"),
                'total_commission': Decimal("0"),
                'previous_settlements': Decimal("0"),
                'pending_amount': Decimal("0")
            }
    
    async def _calculate_deductions(self, agent_id: str, gross_amount: Decimal) -> Decimal:
        """Calculate deductions for agent settlement including configurable fees"""
        deductions = Decimal("0")

        # Apply configurable service fee from fee schedule engine
        try:
            fee_response = await self.http.post(
                f"{FEE_SCHEDULE_SERVICE_URL}/calculate-fee",
                json={
                    "merchant_id": agent_id,
                    "transaction_type": "pos_cash_out",
                    "transaction_amount": float(gross_amount),
                },
                timeout=10.0,
            )
            if fee_response.status_code == 200:
                fee_data = fee_response.json()
                service_fee = Decimal(str(fee_data.get("fee_amount", "0")))
                if service_fee > 0:
                    deductions += service_fee
                    logger.info(f"Applied service fee {service_fee} for agent {agent_id}")
        except Exception as e:
            logger.warning(f"Fee schedule lookup failed for agent {agent_id}: {e}")

        # Check for outstanding loans
        loan_row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(outstanding_amount), 0) as total_loans
            FROM agent_loans
            WHERE agent_id = $1 AND status = 'active'
        """, agent_id)

        if loan_row and loan_row['total_loans'] > 0:
            loan_deduction = min(loan_row['total_loans'], gross_amount * Decimal("0.3"))
            deductions += loan_deduction

        # Check for penalties
        penalty_row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(amount), 0) as total_penalties
            FROM agent_penalties
            WHERE agent_id = $1 AND status = 'pending'
        """, agent_id)

        if penalty_row and penalty_row['total_penalties'] > 0:
            deductions += penalty_row['total_penalties']

        # Check for chargebacks
        chargeback_row = await self.db.fetchrow("""
            SELECT COALESCE(SUM(amount), 0) as total_chargebacks
            FROM transaction_chargebacks
            WHERE agent_id = $1 AND status = 'approved' AND settled = false
        """, agent_id)

        if chargeback_row and chargeback_row['total_chargebacks'] > 0:
            deductions += chargeback_row['total_chargebacks']

        return deductions
    
    async def _get_agent_payout_details(self, agent_id: str) -> Dict[str, Any]:
        """Get agent payout details (bank account, mobile money, etc.)"""
        row = await self.db.fetchrow("""
            SELECT payout_method, bank_name, account_number, account_name,
                   mobile_money_provider, mobile_money_number
            FROM agent_payout_details
            WHERE agent_id = $1
        """, agent_id)
        
        if row:
            return dict(row)
        else:
            # Default payout details
            return {
                'payout_method': 'wallet',
                'bank_name': None,
                'account_number': None,
                'account_name': None,
                'mobile_money_provider': None,
                'mobile_money_number': None
            }
    
    async def _process_payout_tigerbeetle(self, item: Dict) -> str:
        """Process payout via TigerBeetle ledger"""
        try:
            # Convert to kobo (smallest unit)
            amount_kobo = int(item['net_amount'] * 100)
            
            # Create transfer request
            transfer_data = {
                'from_user_id': 'platform_commission_pool',  # Platform commission pool account
                'to_user_id': item['agent_id'],
                'amount': float(item['net_amount']),
                'transaction_type': 'commission_settlement',
                'description': f"Commission settlement for batch {item['batch_id']}",
                'metadata': {
                    'batch_id': item['batch_id'],
                    'settlement_item_id': item['id'],
                    'period_start': str(item.get('period_start', '')),
                    'period_end': str(item.get('period_end', ''))
                }
            }
            
            # Call TigerBeetle service
            response = await self.http.post(
                f"{TIGERBEETLE_SERVICE_URL}/transfer",
                json=transfer_data
            )
            response.raise_for_status()
            result = response.json()
            
            return result['transfer_id']
            
        except Exception as e:
            logger.error(f"TigerBeetle transfer failed for item {item['id']}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process payout via TigerBeetle: {str(e)}"
            )
    
    async def _mark_commissions_settled(
        self, agent_id: str, period_start: date, period_end: date, batch_id: str
    ):
        """Mark commissions as settled in commission service"""
        try:
            # Update commission calculations as settled
            await self.db.execute("""
                UPDATE commission_calculations
                SET settlement_status = 'settled',
                    settlement_batch_id = $1,
                    settled_at = $2
                WHERE agent_id = $3
                  AND calculated_at >= $4
                  AND calculated_at < $5
                  AND settlement_status = 'pending'
            """, batch_id, datetime.utcnow(), agent_id, period_start, period_end + timedelta(days=1))
            
        except Exception as e:
            logger.error(f"Failed to mark commissions as settled: {str(e)}")
    
    async def _send_settlement_notification(self, item: Dict, transfer_id: str):
        """Send settlement notification to agent"""
        try:
            notification_data = {
                'user_id': item['agent_id'],
                'notification_type': 'settlement_completed',
                'title': 'Commission Settlement Processed',
                'message': f"Your commission of ₦{item['net_amount']:,.2f} has been settled.",
                'data': {
                    'settlement_item_id': item['id'],
                    'amount': float(item['net_amount']),
                    'transfer_id': transfer_id
                }
            }
            
            await self.http.post(
                f"{NOTIFICATION_SERVICE_URL}/notifications/send",
                json=notification_data
            )
        except Exception as e:
            logger.warning(f"Failed to send settlement notification: {str(e)}")
    
    async def _auto_approve_batch(self, batch_id: str, approver_id: str):
        """Auto-approve batch"""
        await self.db.execute("""
            UPDATE settlement_batches
            SET status = $1, approved_by = $2, approved_at = $3, updated_at = $4
            WHERE id = $5
        """, SettlementStatus.APPROVED, approver_id, datetime.utcnow(),
            datetime.utcnow(), batch_id)
        logger.info(f"Auto-approved settlement batch {batch_id}")

# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/settlement/rules", response_model=SettlementRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_settlement_rule(rule_data: SettlementRuleCreate):
    """Create a new settlement rule"""
    conn = await get_db_connection()
    try:
        rule_id = str(uuid.uuid4())
        
        await conn.execute("""
            INSERT INTO settlement_rules (
                id, rule_name, description, frequency, settlement_day, settlement_weekday,
                min_settlement_amount, auto_approve, auto_approve_threshold, payout_method,
                is_active, agent_tier, territory_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """, rule_id, rule_data.rule_name, rule_data.description, rule_data.frequency.value,
            rule_data.settlement_day, rule_data.settlement_weekday, rule_data.min_settlement_amount,
            rule_data.auto_approve, rule_data.auto_approve_threshold, rule_data.payout_method.value,
            rule_data.is_active, rule_data.agent_tier, rule_data.territory_id,
            datetime.utcnow(), datetime.utcnow())
        
        # Fetch created rule
        rule = await conn.fetchrow("SELECT * FROM settlement_rules WHERE id = $1", rule_id)
        
        logger.info(f"Created settlement rule: {rule_id}")
        return dict(rule)
        
    finally:
        await release_db_connection(conn)

@app.get("/settlement/rules", response_model=List[SettlementRuleResponse])
async def list_settlement_rules(
    is_active: Optional[bool] = None,
    frequency: Optional[SettlementFrequency] = None
):
    """List settlement rules"""
    conn = await get_db_connection()
    try:
        query = "SELECT * FROM settlement_rules WHERE 1=1"
        params = []
        
        if is_active is not None:
            params.append(is_active)
            query += f" AND is_active = ${len(params)}"
        
        if frequency:
            params.append(frequency.value)
            query += f" AND frequency = ${len(params)}"
        
        query += " ORDER BY created_at DESC"
        
        rules = await conn.fetch(query, *params)
        return [dict(rule) for rule in rules]
        
    finally:
        await release_db_connection(conn)

@app.post("/settlement/batches", response_model=SettlementBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_settlement_batch(
    batch_data: SettlementBatchCreate,
    created_by: str = "system",
    background_tasks: BackgroundTasks = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """Create a new settlement batch. Send Idempotency-Key header to prevent duplicates."""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = SettlementEngine(conn, redis_conn, http)
        batch_id = await engine.create_settlement_batch(batch_data, created_by, idempotency_key=idempotency_key)
        
        # Fetch created batch
        batch = await conn.fetchrow("SELECT * FROM settlement_batches WHERE id = $1", batch_id)
        
        return dict(batch)
        
    finally:
        await release_db_connection(conn)

@app.get("/settlement/batches", response_model=List[SettlementBatchResponse])
async def list_settlement_batches(
    status_filter: Optional[SettlementStatus] = None,
    limit: int = Query(50, ge=1, le=100)
):
    """List settlement batches"""
    conn = await get_db_connection()
    try:
        query = "SELECT * FROM settlement_batches WHERE 1=1"
        params = []
        
        if status_filter:
            params.append(status_filter.value)
            query += f" AND status = ${len(params)}"
        
        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        batches = await conn.fetch(query, *params)
        return [dict(batch) for batch in batches]
        
    finally:
        await release_db_connection(conn)

@app.get("/settlement/batches/{batch_id}", response_model=SettlementBatchResponse)
async def get_settlement_batch(batch_id: str):
    """Get settlement batch details"""
    conn = await get_db_connection()
    try:
        batch = await conn.fetchrow("SELECT * FROM settlement_batches WHERE id = $1", batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Settlement batch not found")
        return dict(batch)
    finally:
        await release_db_connection(conn)

@app.get("/settlement/batches/{batch_id}/items", response_model=List[SettlementItemResponse])
async def get_settlement_batch_items(batch_id: str):
    """Get settlement batch items"""
    conn = await get_db_connection()
    try:
        items = await conn.fetch("""
            SELECT si.*, a.name as agent_name
            FROM settlement_items si
            LEFT JOIN agents a ON si.agent_id = a.id
            WHERE si.batch_id = $1
            ORDER BY si.created_at
        """, batch_id)
        
        return [dict(item) for item in items]
    finally:
        await release_db_connection(conn)

@app.post("/settlement/batches/{batch_id}/approve")
async def approve_settlement_batch(batch_id: str, approval: SettlementApprovalRequest):
    """Approve or reject a settlement batch"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = SettlementEngine(conn, redis_conn, http)
        result = await engine.approve_settlement_batch(batch_id, approval)
        
        return {
            'batch_id': batch_id,
            'approved': result,
            'message': 'Batch approved' if result else 'Batch rejected'
        }
    finally:
        await release_db_connection(conn)

@app.post("/settlement/batches/{batch_id}/process")
async def process_settlement_batch(
    batch_id: str,
    process_request: SettlementProcessRequest,
    background_tasks: BackgroundTasks
):
    """Process an approved settlement batch"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = SettlementEngine(conn, redis_conn, http)
        
        # Process in background
        background_tasks.add_task(
            engine.process_settlement_batch,
            batch_id,
            process_request.notify_agents
        )
        
        return {
            'batch_id': batch_id,
            'message': 'Settlement processing started',
            'status': 'processing'
        }
    finally:
        await release_db_connection(conn)

@app.post("/settlement/batches/{batch_id}/retry")
async def retry_failed_settlements(batch_id: str, background_tasks: BackgroundTasks):
    """Retry failed settlement items"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = SettlementEngine(conn, redis_conn, http)
        result = await engine.retry_failed_settlements(batch_id)
        
        return result
    finally:
        await release_db_connection(conn)

@app.get("/settlement/agents/{agent_id}/summary", response_model=CommissionSummaryResponse)
async def get_agent_settlement_summary(
    agent_id: str,
    period_start: date,
    period_end: date
):
    """Get agent settlement summary"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = SettlementEngine(conn, redis_conn, http)
        summary = await engine._get_agent_commission_summary(agent_id, period_start, period_end)
        
        return summary
    finally:
        await release_db_connection(conn)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "settlement-service",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    conn = await get_db_connection()
    try:
        total_batches = await conn.fetchval("SELECT COUNT(*) FROM settlement_batches")
        pending_batches = await conn.fetchval(
            "SELECT COUNT(*) FROM settlement_batches WHERE status = $1",
            SettlementStatus.PENDING
        )
        completed_batches = await conn.fetchval(
            "SELECT COUNT(*) FROM settlement_batches WHERE status = $1",
            SettlementStatus.COMPLETED
        )
        
        return {
            'total_batches': total_batches or 0,
            'pending_batches': pending_batches or 0,
            'completed_batches': completed_batches or 0,
            'timestamp': datetime.utcnow().isoformat()
        }
    finally:
        await release_db_connection(conn)

# =====================================================
# STARTUP AND SHUTDOWN
# =====================================================

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global db_pool, redis_client, http_client
    logger.info("Starting Settlement Service...")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    redis_client = redis.from_url(REDIS_URL)
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Settlement Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    global db_pool, redis_client, http_client
    logger.info("Shutting down Settlement Service...")
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()
    logger.info("Settlement Service shut down successfully")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8020))
    uvicorn.run(app, host="0.0.0.0", port=port)

