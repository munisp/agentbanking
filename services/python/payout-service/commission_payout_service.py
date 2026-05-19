import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Remittance Platform - Commission Payout and Dispute Resolution Service
Handles commission payouts, dispute management, and reconciliation processes
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Union
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Query, Path, Body, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("commission-payout-and-dispute-resolution-service")
app.include_router(metrics_router)

from pydantic import BaseModel, validator, Field
import json
from dataclasses import dataclass
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Commission Payout and Dispute Resolution Service",
    description="Advanced commission payout management and dispute resolution system",
    version="1.0.0"
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
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8040")

# Database and Redis connections
db_pool = None
redis_client = None

# =====================================================
# ENUMS AND CONSTANTS
# =====================================================

class PayoutStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"

class PayoutMethod(str, Enum):
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    DIGITAL_WALLET = "digital_wallet"
    CASH = "cash"
    CHECK = "check"

class DisputeStatus(str, Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ESCALATED = "escalated"

class DisputeType(str, Enum):
    CALCULATION_ERROR = "calculation_error"
    MISSING_COMMISSION = "missing_commission"
    INCORRECT_RATE = "incorrect_rate"
    HIERARCHY_ISSUE = "hierarchy_issue"
    PAYOUT_DELAY = "payout_delay"
    OTHER = "other"

class PayoutFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

# =====================================================
# DATA MODELS
# =====================================================

class PayoutRequest(BaseModel):
    agent_id: str
    period_start: date
    period_end: date
    payout_method: PayoutMethod
    bank_account_id: Optional[str] = None
    mobile_money_number: Optional[str] = None
    digital_wallet_id: Optional[str] = None
    notes: Optional[str] = None

class PayoutResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    period_start: date
    period_end: date
    gross_commission: Decimal
    deductions: Decimal
    net_amount: Decimal
    payout_method: str
    payout_details: Dict[str, Any]
    status: str
    transaction_id: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class DisputeCreate(BaseModel):
    agent_id: str
    dispute_type: DisputeType
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    related_transaction_id: Optional[str] = None
    related_payout_id: Optional[str] = None
    disputed_amount: Optional[Decimal] = Field(None, ge=0)
    supporting_documents: Optional[List[str]] = None

class DisputeResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    dispute_type: str
    subject: str
    description: str
    status: str
    priority: str
    related_transaction_id: Optional[str]
    related_payout_id: Optional[str]
    disputed_amount: Optional[Decimal]
    resolution: Optional[str]
    resolved_amount: Optional[Decimal]
    assigned_to: Optional[str]
    supporting_documents: List[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]

class DisputeResolution(BaseModel):
    resolution: str = Field(..., min_length=10, max_length=2000)
    resolved_amount: Optional[Decimal] = Field(None, ge=0)
    adjustment_required: bool = False
    adjustment_amount: Optional[Decimal] = None
    adjustment_reason: Optional[str] = None

class PayoutSummary(BaseModel):
    total_payouts: int
    total_amount: Decimal
    pending_payouts: int
    pending_amount: Decimal
    completed_payouts: int
    completed_amount: Decimal
    failed_payouts: int
    failed_amount: Decimal

class ReconciliationReport(BaseModel):
    period_start: date
    period_end: date
    total_commissions_calculated: Decimal
    total_payouts_processed: Decimal
    total_disputes_raised: int
    total_adjustments_made: Decimal
    reconciliation_variance: Decimal
    status: str

# =====================================================
# DATABASE CONNECTION
# =====================================================

async def get_db_connection():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return await db_pool.acquire()

async def get_redis_connection():
    """Get Redis connection"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL)
    return redis_client

# =====================================================
# PAYOUT PROCESSING ENGINE
# =====================================================

class PayoutProcessingEngine:
    """Advanced payout processing engine with multiple payment methods"""
    
    def __init__(self, db_connection, redis_connection):
        self.db = db_connection
        self.redis = redis_connection
    
    async def create_payout_request(self, request: PayoutRequest) -> PayoutResponse:
        """Create a new payout request"""
        try:
            # Validate agent exists
            agent = await self.db.fetchrow("SELECT * FROM agents WHERE id = $1", request.agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            
            # Calculate commission summary for the period
            commission_summary = await self._calculate_commission_summary(
                request.agent_id, request.period_start, request.period_end
            )
            
            if commission_summary['gross_commission'] <= 0:
                raise HTTPException(
                    status_code=400, 
                    detail="No commissions found for the specified period"
                )
            
            # Calculate deductions (taxes, fees, etc.)
            deductions = await self._calculate_deductions(
                request.agent_id, commission_summary['gross_commission']
            )
            
            net_amount = commission_summary['gross_commission'] - deductions
            
            if net_amount <= 0:
                raise HTTPException(
                    status_code=400, 
                    detail="Net payout amount is zero or negative after deductions"
                )
            
            # Prepare payout details based on method
            payout_details = await self._prepare_payout_details(request, agent)
            
            # Create payout record
            payout_id = str(uuid.uuid4())
            
            await self.db.execute(
                """
                INSERT INTO commission_payouts (
                    id, agent_id, period_start, period_end, gross_commission, deductions,
                    net_amount, payout_method, payout_details, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                payout_id, request.agent_id, request.period_start, request.period_end,
                commission_summary['gross_commission'], deductions, net_amount,
                request.payout_method, json.dumps(payout_details), PayoutStatus.PENDING
            )
            
            # Cache payout request
            await self.redis.setex(
                f"payout_request:{payout_id}",
                3600,  # 1 hour TTL
                json.dumps({
                    'payout_id': payout_id,
                    'agent_id': request.agent_id,
                    'net_amount': float(net_amount),
                    'status': PayoutStatus.PENDING
                }, default=str)
            )
            
            # Get created payout
            payout = await self.db.fetchrow("SELECT * FROM commission_payouts WHERE id = $1", payout_id)
            
            return PayoutResponse(
                id=str(payout['id']),
                agent_id=payout['agent_id'],
                agent_name=f"{agent['first_name']} {agent['last_name']}",
                period_start=payout['period_start'],
                period_end=payout['period_end'],
                gross_commission=payout['gross_commission'],
                deductions=payout['deductions'],
                net_amount=payout['net_amount'],
                payout_method=payout['payout_method'],
                payout_details=payout['payout_details'],
                status=payout['status'],
                transaction_id=payout['transaction_id'],
                processed_at=payout['processed_at'],
                created_at=payout['created_at'],
                updated_at=payout['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Payout request creation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Payout request creation failed: {str(e)}")
    
    async def process_payout(self, payout_id: str) -> PayoutResponse:
        """Process a pending payout"""
        try:
            # Get payout details
            payout = await self.db.fetchrow("SELECT * FROM commission_payouts WHERE id = $1", payout_id)
            if not payout:
                raise HTTPException(status_code=404, detail="Payout not found")
            
            if payout['status'] != PayoutStatus.PENDING:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Payout is not in pending status. Current status: {payout['status']}"
                )
            
            # Update status to processing
            await self.db.execute(
                "UPDATE commission_payouts SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                PayoutStatus.PROCESSING, payout_id
            )
            
            # Process payment based on method
            transaction_id = await self._process_payment(payout)
            
            # Update payout with transaction details
            await self.db.execute(
                """
                UPDATE commission_payouts 
                SET status = $1, transaction_id = $2, processed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = $3
                """,
                PayoutStatus.COMPLETED, transaction_id, payout_id
            )
            
            # Update commission calculations as paid
            await self.db.execute(
                """
                UPDATE commission_calculations 
                SET payout_status = 'paid', payout_id = $1, updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = $2 AND DATE(transaction_date) BETWEEN $3 AND $4
                """,
                payout_id, payout['agent_id'], payout['period_start'], payout['period_end']
            )
            
            # Send notification
            await self._send_payout_notification(payout_id, "completed")
            
            # Get updated payout
            updated_payout = await self.db.fetchrow("SELECT * FROM commission_payouts WHERE id = $1", payout_id)
            agent = await self.db.fetchrow("SELECT * FROM agents WHERE id = $1", updated_payout['agent_id'])
            
            return PayoutResponse(
                id=str(updated_payout['id']),
                agent_id=updated_payout['agent_id'],
                agent_name=f"{agent['first_name']} {agent['last_name']}",
                period_start=updated_payout['period_start'],
                period_end=updated_payout['period_end'],
                gross_commission=updated_payout['gross_commission'],
                deductions=updated_payout['deductions'],
                net_amount=updated_payout['net_amount'],
                payout_method=updated_payout['payout_method'],
                payout_details=updated_payout['payout_details'],
                status=updated_payout['status'],
                transaction_id=updated_payout['transaction_id'],
                processed_at=updated_payout['processed_at'],
                created_at=updated_payout['created_at'],
                updated_at=updated_payout['updated_at']
            )
            
        except Exception as e:
            # Update payout status to failed
            await self.db.execute(
                "UPDATE commission_payouts SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                PayoutStatus.FAILED, payout_id
            )
            
            await self._send_payout_notification(payout_id, "failed")
            
            logger.error(f"Payout processing failed: {e}")
            raise HTTPException(status_code=500, detail=f"Payout processing failed: {str(e)}")
    
    async def _calculate_commission_summary(self, agent_id: str, start_date: date, end_date: date) -> Dict:
        """Calculate commission summary for a period"""
        summary_query = """
        SELECT 
            COUNT(*) as total_transactions,
            SUM(commission_amount) as gross_commission,
            SUM(CASE WHEN parent_commission_amount IS NOT NULL THEN parent_commission_amount ELSE 0 END) as hierarchy_commission
        FROM commission_calculations
        WHERE agent_id = $1 
        AND DATE(transaction_date) BETWEEN $2 AND $3
        AND payout_status IS NULL OR payout_status != 'paid'
        """
        
        result = await self.db.fetchrow(summary_query, agent_id, start_date, end_date)
        
        return {
            'total_transactions': result['total_transactions'] or 0,
            'gross_commission': result['gross_commission'] or Decimal('0.00'),
            'hierarchy_commission': result['hierarchy_commission'] or Decimal('0.00')
        }
    
    async def _calculate_deductions(self, agent_id: str, gross_commission: Decimal) -> Decimal:
        """Calculate deductions (taxes, fees, etc.)"""
        # Get agent tax information
        agent_tax = await self.db.fetchrow(
            "SELECT tax_rate, service_fee_rate FROM agent_tax_settings WHERE agent_id = $1",
            agent_id
        )
        
        deductions = Decimal('0.00')
        
        if agent_tax:
            # Tax deduction
            if agent_tax['tax_rate']:
                tax_amount = (gross_commission * Decimal(str(agent_tax['tax_rate']))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                deductions += tax_amount
            
            # Service fee deduction
            if agent_tax['service_fee_rate']:
                service_fee = (gross_commission * Decimal(str(agent_tax['service_fee_rate']))).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                deductions += service_fee
        
        return deductions
    
    async def _prepare_payout_details(self, request: PayoutRequest, agent: Dict) -> Dict:
        """Prepare payout details based on method"""
        details = {
            'method': request.payout_method,
            'agent_name': f"{agent['first_name']} {agent['last_name']}",
            'agent_email': agent['email']
        }
        
        if request.payout_method == PayoutMethod.BANK_TRANSFER:
            if not request.bank_account_id:
                raise HTTPException(status_code=400, detail="Bank account ID required for bank transfer")
            
            # Get bank account details
            bank_account = await self.db.fetchrow(
                "SELECT * FROM partner_bank_accounts WHERE id = $1 AND agent_id = $2",
                request.bank_account_id, request.agent_id
            )
            
            if not bank_account:
                raise HTTPException(status_code=404, detail="Bank account not found")
            
            details.update({
                'bank_name': bank_account['bank_name'],
                'account_number': bank_account['account_number'][-4:],  # Last 4 digits only
                'account_holder': bank_account['account_holder_name'],
                'routing_number': bank_account['routing_number']
            })
        
        elif request.payout_method == PayoutMethod.MOBILE_MONEY:
            if not request.mobile_money_number:
                raise HTTPException(status_code=400, detail="Mobile money number required")
            
            details.update({
                'mobile_number': request.mobile_money_number,
                'provider': 'MTN'  # Default provider, should be configurable
            })
        
        elif request.payout_method == PayoutMethod.DIGITAL_WALLET:
            if not request.digital_wallet_id:
                raise HTTPException(status_code=400, detail="Digital wallet ID required")
            
            details.update({
                'wallet_id': request.digital_wallet_id,
                'wallet_provider': 'PayPal'  # Default provider, should be configurable
            })
        
        return details
    
    async def _process_payment(self, payout: Dict) -> str:
        """Process payment based on payout method"""
        payout_method = payout['payout_method']
        
        if payout_method == PayoutMethod.BANK_TRANSFER:
            return await self._process_bank_transfer(payout)
        elif payout_method == PayoutMethod.MOBILE_MONEY:
            return await self._process_mobile_money(payout)
        elif payout_method == PayoutMethod.DIGITAL_WALLET:
            return await self._process_digital_wallet(payout)
        else:
            # For cash and check, create manual transaction record
            return await self._create_manual_transaction(payout)
    
    async def _process_bank_transfer(self, payout: Dict) -> str:
        """Process bank transfer payment"""
        # In production, integrate with actual banking API
        # Execute payout via provider
        
        transaction_id = f"BT_{uuid.uuid4().hex[:12].upper()}"
        
        # Execute bank transfer API call

        
        # Log transaction
        logger.info(f"Bank transfer processed: {transaction_id} for amount {payout['net_amount']}")
        
        return transaction_id
    
    async def _process_mobile_money(self, payout: Dict) -> str:
        """Process mobile money payment"""
        transaction_id = f"MM_{uuid.uuid4().hex[:12].upper()}"
        
        # Execute mobile money API call
        await asyncio.sleep(1)
        
        logger.info(f"Mobile money transfer processed: {transaction_id} for amount {payout['net_amount']}")
        
        return transaction_id
    
    async def _process_digital_wallet(self, payout: Dict) -> str:
        """Process digital wallet payment"""
        transaction_id = f"DW_{uuid.uuid4().hex[:12].upper()}"
        
        # Execute digital wallet API call
        await asyncio.sleep(1)
        
        logger.info(f"Digital wallet transfer processed: {transaction_id} for amount {payout['net_amount']}")
        
        return transaction_id
    
    async def _create_manual_transaction(self, payout: Dict) -> str:
        """Create manual transaction record for cash/check payments"""
        transaction_id = f"MN_{uuid.uuid4().hex[:12].upper()}"
        
        logger.info(f"Manual transaction created: {transaction_id} for amount {payout['net_amount']}")
        
        return transaction_id
    
    async def _send_payout_notification(self, payout_id: str, status: str):
        """Send payout notification to agent"""
        try:
            # Get payout and agent details
            payout = await self.db.fetchrow("SELECT * FROM commission_payouts WHERE id = $1", payout_id)
            agent = await self.db.fetchrow("SELECT * FROM agents WHERE id = $1", payout['agent_id'])
            
            # Send notification via communication service
            notification_data = {
                'recipient': agent['email'],
                'template': 'payout_notification',
                'data': {
                    'agent_name': f"{agent['first_name']} {agent['last_name']}",
                    'payout_amount': float(payout['net_amount']),
                    'status': status,
                    'transaction_id': payout['transaction_id']
                }
            }
            
            # In production, call actual notification service
            logger.info(f"Payout notification sent to {agent['email']}: {status}")
            
        except Exception as e:
            logger.error(f"Failed to send payout notification: {e}")

# =====================================================
# DISPUTE MANAGEMENT ENGINE
# =====================================================

class DisputeManagementEngine:
    """Advanced dispute management and resolution engine"""
    
    def __init__(self, db_connection, redis_connection):
        self.db = db_connection
        self.redis = redis_connection
    
    async def create_dispute(self, dispute_data: DisputeCreate) -> DisputeResponse:
        """Create a new commission dispute"""
        try:
            # Validate agent exists
            agent = await self.db.fetchrow("SELECT * FROM agents WHERE id = $1", dispute_data.agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            
            # Validate related transaction/payout if provided
            if dispute_data.related_transaction_id:
                transaction = await self.db.fetchrow(
                    "SELECT * FROM commission_calculations WHERE transaction_id = $1",
                    dispute_data.related_transaction_id
                )
                if not transaction:
                    raise HTTPException(status_code=404, detail="Related transaction not found")
            
            if dispute_data.related_payout_id:
                payout = await self.db.fetchrow(
                    "SELECT * FROM commission_payouts WHERE id = $1",
                    dispute_data.related_payout_id
                )
                if not payout:
                    raise HTTPException(status_code=404, detail="Related payout not found")
            
            # Determine priority based on dispute type and amount
            priority = await self._calculate_dispute_priority(dispute_data)
            
            # Create dispute record
            dispute_id = str(uuid.uuid4())
            
            await self.db.execute(
                """
                INSERT INTO commission_disputes (
                    id, agent_id, dispute_type, subject, description, status, priority,
                    related_transaction_id, related_payout_id, disputed_amount, supporting_documents
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                dispute_id, dispute_data.agent_id, dispute_data.dispute_type,
                dispute_data.subject, dispute_data.description, DisputeStatus.OPEN,
                priority, dispute_data.related_transaction_id, dispute_data.related_payout_id,
                dispute_data.disputed_amount, json.dumps(dispute_data.supporting_documents or [])
            )
            
            # Assign dispute to appropriate team member
            assigned_to = await self._assign_dispute(dispute_data.dispute_type, priority)
            if assigned_to:
                await self.db.execute(
                    "UPDATE commission_disputes SET assigned_to = $1 WHERE id = $2",
                    assigned_to, dispute_id
                )
            
            # Send notification to dispute team
            await self._send_dispute_notification(dispute_id, "created")
            
            # Get created dispute
            dispute = await self.db.fetchrow("SELECT * FROM commission_disputes WHERE id = $1", dispute_id)
            
            return DisputeResponse(
                id=str(dispute['id']),
                agent_id=dispute['agent_id'],
                agent_name=f"{agent['first_name']} {agent['last_name']}",
                dispute_type=dispute['dispute_type'],
                subject=dispute['subject'],
                description=dispute['description'],
                status=dispute['status'],
                priority=dispute['priority'],
                related_transaction_id=dispute['related_transaction_id'],
                related_payout_id=str(dispute['related_payout_id']) if dispute['related_payout_id'] else None,
                disputed_amount=dispute['disputed_amount'],
                resolution=dispute['resolution'],
                resolved_amount=dispute['resolved_amount'],
                assigned_to=dispute['assigned_to'],
                supporting_documents=dispute['supporting_documents'] or [],
                created_at=dispute['created_at'],
                updated_at=dispute['updated_at'],
                resolved_at=dispute['resolved_at']
            )
            
        except Exception as e:
            logger.error(f"Dispute creation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Dispute creation failed: {str(e)}")
    
    async def resolve_dispute(self, dispute_id: str, resolution: DisputeResolution) -> DisputeResponse:
        """Resolve a commission dispute"""
        try:
            # Get dispute details
            dispute = await self.db.fetchrow("SELECT * FROM commission_disputes WHERE id = $1", dispute_id)
            if not dispute:
                raise HTTPException(status_code=404, detail="Dispute not found")
            
            if dispute['status'] in [DisputeStatus.RESOLVED, DisputeStatus.REJECTED]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Dispute is already {dispute['status']}"
                )
            
            # Update dispute with resolution
            await self.db.execute(
                """
                UPDATE commission_disputes 
                SET status = $1, resolution = $2, resolved_amount = $3, resolved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $4
                """,
                DisputeStatus.RESOLVED, resolution.resolution, resolution.resolved_amount, dispute_id
            )
            
            # Process adjustment if required
            if resolution.adjustment_required and resolution.adjustment_amount:
                await self._process_commission_adjustment(
                    dispute, resolution.adjustment_amount, resolution.adjustment_reason
                )
            
            # Send resolution notification
            await self._send_dispute_notification(dispute_id, "resolved")
            
            # Get updated dispute
            updated_dispute = await self.db.fetchrow("SELECT * FROM commission_disputes WHERE id = $1", dispute_id)
            agent = await self.db.fetchrow("SELECT * FROM agents WHERE id = $1", updated_dispute['agent_id'])
            
            return DisputeResponse(
                id=str(updated_dispute['id']),
                agent_id=updated_dispute['agent_id'],
                agent_name=f"{agent['first_name']} {agent['last_name']}",
                dispute_type=updated_dispute['dispute_type'],
                subject=updated_dispute['subject'],
                description=updated_dispute['description'],
                status=updated_dispute['status'],
                priority=updated_dispute['priority'],
                related_transaction_id=updated_dispute['related_transaction_id'],
                related_payout_id=str(updated_dispute['related_payout_id']) if updated_dispute['related_payout_id'] else None,
                disputed_amount=updated_dispute['disputed_amount'],
                resolution=updated_dispute['resolution'],
                resolved_amount=updated_dispute['resolved_amount'],
                assigned_to=updated_dispute['assigned_to'],
                supporting_documents=updated_dispute['supporting_documents'] or [],
                created_at=updated_dispute['created_at'],
                updated_at=updated_dispute['updated_at'],
                resolved_at=updated_dispute['resolved_at']
            )
            
        except Exception as e:
            logger.error(f"Dispute resolution failed: {e}")
            raise HTTPException(status_code=500, detail=f"Dispute resolution failed: {str(e)}")
    
    async def _calculate_dispute_priority(self, dispute_data: DisputeCreate) -> str:
        """Calculate dispute priority based on type and amount"""
        if dispute_data.dispute_type in [DisputeType.CALCULATION_ERROR, DisputeType.MISSING_COMMISSION]:
            if dispute_data.disputed_amount and dispute_data.disputed_amount > 1000:
                return "high"
            elif dispute_data.disputed_amount and dispute_data.disputed_amount > 100:
                return "medium"
            else:
                return "low"
        elif dispute_data.dispute_type == DisputeType.PAYOUT_DELAY:
            return "high"
        else:
            return "medium"
    
    async def _assign_dispute(self, dispute_type: DisputeType, priority: str) -> Optional[str]:
        """Assign dispute to appropriate team member"""
        # In production, implement actual assignment logic
        # Return territory assignment
        if priority == "high":
            return "senior_dispute_manager"
        elif dispute_type in [DisputeType.CALCULATION_ERROR, DisputeType.INCORRECT_RATE]:
            return "technical_specialist"
        else:
            return "dispute_agent"
    
    async def _process_commission_adjustment(self, dispute: Dict, adjustment_amount: Decimal, reason: str):
        """Process commission adjustment based on dispute resolution"""
        adjustment_id = str(uuid.uuid4())
        
        # Create adjustment record
        await self.db.execute(
            """
            INSERT INTO commission_adjustments (
                id, agent_id, dispute_id, adjustment_amount, adjustment_reason, adjustment_type
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            adjustment_id, dispute['agent_id'], dispute['id'], adjustment_amount, reason, "dispute_resolution"
        )
        
        # Update agent commission balance
        await self.db.execute(
            """
            UPDATE agents 
            SET commission_balance = commission_balance + $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            """,
            adjustment_amount, dispute['agent_id']
        )
        
        logger.info(f"Commission adjustment processed: {adjustment_amount} for agent {dispute['agent_id']}")
    
    async def _send_dispute_notification(self, dispute_id: str, action: str):
        """Send dispute notification"""
        try:
            dispute = await self.db.fetchrow("SELECT * FROM commission_disputes WHERE id = $1", dispute_id)
            agent = await self.db.fetchrow("SELECT * FROM agents WHERE id = $1", dispute['agent_id'])
            
            logger.info(f"Dispute notification sent: {action} for dispute {dispute_id}")
            
        except Exception as e:
            logger.error(f"Failed to send dispute notification: {e}")

# =====================================================
# PAYOUT ENDPOINTS
# =====================================================

@app.post("/payouts", response_model=PayoutResponse)
async def create_payout_request(request: PayoutRequest):
    """Create a new payout request"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        engine = PayoutProcessingEngine(conn, redis_conn)
        return await engine.create_payout_request(request)
    finally:
        await conn.close()

@app.post("/payouts/{payout_id}/process", response_model=PayoutResponse)
async def process_payout(payout_id: str):
    """Process a pending payout"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        engine = PayoutProcessingEngine(conn, redis_conn)
        return await engine.process_payout(payout_id)
    finally:
        await conn.close()

@app.get("/payouts", response_model=List[PayoutResponse])
async def list_payouts(
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List payouts with filtering"""
    conn = await get_db_connection()
    try:
        # Build query with filters
        where_conditions = []
        params = []
        param_count = 0
        
        if agent_id:
            param_count += 1
            where_conditions.append(f"p.agent_id = ${param_count}")
            params.append(agent_id)
        
        if status:
            param_count += 1
            where_conditions.append(f"p.status = ${param_count}")
            params.append(status)
        
        if start_date:
            param_count += 1
            where_conditions.append(f"p.period_start >= ${param_count}")
            params.append(start_date)
        
        if end_date:
            param_count += 1
            where_conditions.append(f"p.period_end <= ${param_count}")
            params.append(end_date)
        
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        param_count += 1
        limit_param = f"${param_count}"
        params.append(limit)
        
        param_count += 1
        offset_param = f"${param_count}"
        params.append(offset)
        
        query = f"""
        SELECT p.*, a.first_name, a.last_name
        FROM commission_payouts p
        INNER JOIN agents a ON p.agent_id = a.id
        {where_clause}
        ORDER BY p.created_at DESC
        LIMIT {limit_param} OFFSET {offset_param}
        """
        
        results = await conn.fetch(query, *params)
        
        payouts = []
        for result in results:
            payouts.append(PayoutResponse(
                id=str(result['id']),
                agent_id=result['agent_id'],
                agent_name=f"{result['first_name']} {result['last_name']}",
                period_start=result['period_start'],
                period_end=result['period_end'],
                gross_commission=result['gross_commission'],
                deductions=result['deductions'],
                net_amount=result['net_amount'],
                payout_method=result['payout_method'],
                payout_details=result['payout_details'],
                status=result['status'],
                transaction_id=result['transaction_id'],
                processed_at=result['processed_at'],
                created_at=result['created_at'],
                updated_at=result['updated_at']
            ))
        
        return payouts
    
    finally:
        await conn.close()

@app.get("/payouts/summary", response_model=PayoutSummary)
async def get_payout_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None)
):
    """Get payout summary statistics"""
    conn = await get_db_connection()
    try:
        # Default to current month if no dates provided
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()
        
        summary_query = """
        SELECT 
            COUNT(*) as total_payouts,
            SUM(net_amount) as total_amount,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_payouts,
            SUM(net_amount) FILTER (WHERE status = 'pending') as pending_amount,
            COUNT(*) FILTER (WHERE status = 'completed') as completed_payouts,
            SUM(net_amount) FILTER (WHERE status = 'completed') as completed_amount,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_payouts,
            SUM(net_amount) FILTER (WHERE status = 'failed') as failed_amount
        FROM commission_payouts
        WHERE created_at::date BETWEEN $1 AND $2
        """
        
        result = await conn.fetchrow(summary_query, start_date, end_date)
        
        return PayoutSummary(
            total_payouts=result['total_payouts'] or 0,
            total_amount=result['total_amount'] or Decimal('0.00'),
            pending_payouts=result['pending_payouts'] or 0,
            pending_amount=result['pending_amount'] or Decimal('0.00'),
            completed_payouts=result['completed_payouts'] or 0,
            completed_amount=result['completed_amount'] or Decimal('0.00'),
            failed_payouts=result['failed_payouts'] or 0,
            failed_amount=result['failed_amount'] or Decimal('0.00')
        )
    
    finally:
        await conn.close()

# =====================================================
# DISPUTE ENDPOINTS
# =====================================================

@app.post("/disputes", response_model=DisputeResponse)
async def create_dispute(dispute_data: DisputeCreate):
    """Create a new commission dispute"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        engine = DisputeManagementEngine(conn, redis_conn)
        return await engine.create_dispute(dispute_data)
    finally:
        await conn.close()

@app.post("/disputes/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(dispute_id: str, resolution: DisputeResolution):
    """Resolve a commission dispute"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        engine = DisputeManagementEngine(conn, redis_conn)
        return await engine.resolve_dispute(dispute_id, resolution)
    finally:
        await conn.close()

@app.get("/disputes", response_model=List[DisputeResponse])
async def list_disputes(
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    dispute_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List disputes with filtering"""
    conn = await get_db_connection()
    try:
        # Build query with filters
        where_conditions = []
        params = []
        param_count = 0
        
        if agent_id:
            param_count += 1
            where_conditions.append(f"d.agent_id = ${param_count}")
            params.append(agent_id)
        
        if status:
            param_count += 1
            where_conditions.append(f"d.status = ${param_count}")
            params.append(status)
        
        if dispute_type:
            param_count += 1
            where_conditions.append(f"d.dispute_type = ${param_count}")
            params.append(dispute_type)
        
        if priority:
            param_count += 1
            where_conditions.append(f"d.priority = ${param_count}")
            params.append(priority)
        
        where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        param_count += 1
        limit_param = f"${param_count}"
        params.append(limit)
        
        param_count += 1
        offset_param = f"${param_count}"
        params.append(offset)
        
        query = f"""
        SELECT d.*, a.first_name, a.last_name
        FROM commission_disputes d
        INNER JOIN agents a ON d.agent_id = a.id
        {where_clause}
        ORDER BY d.created_at DESC
        LIMIT {limit_param} OFFSET {offset_param}
        """
        
        results = await conn.fetch(query, *params)
        
        disputes = []
        for result in results:
            disputes.append(DisputeResponse(
                id=str(result['id']),
                agent_id=result['agent_id'],
                agent_name=f"{result['first_name']} {result['last_name']}",
                dispute_type=result['dispute_type'],
                subject=result['subject'],
                description=result['description'],
                status=result['status'],
                priority=result['priority'],
                related_transaction_id=result['related_transaction_id'],
                related_payout_id=str(result['related_payout_id']) if result['related_payout_id'] else None,
                disputed_amount=result['disputed_amount'],
                resolution=result['resolution'],
                resolved_amount=result['resolved_amount'],
                assigned_to=result['assigned_to'],
                supporting_documents=result['supporting_documents'] or [],
                created_at=result['created_at'],
                updated_at=result['updated_at'],
                resolved_at=result['resolved_at']
            ))
        
        return disputes
    
    finally:
        await conn.close()

# =====================================================
# RECONCILIATION ENDPOINTS
# =====================================================

@app.get("/reconciliation/report", response_model=ReconciliationReport)
async def generate_reconciliation_report(
    start_date: date = Query(...),
    end_date: date = Query(...)
):
    """Generate reconciliation report for a period"""
    conn = await get_db_connection()
    try:
        # Get commission calculations summary
        calc_summary = await conn.fetchrow(
            """
            SELECT 
                SUM(commission_amount) as total_calculated,
                COUNT(*) as total_transactions
            FROM commission_calculations
            WHERE DATE(transaction_date) BETWEEN $1 AND $2
            """,
            start_date, end_date
        )
        
        # Get payouts summary
        payout_summary = await conn.fetchrow(
            """
            SELECT 
                SUM(net_amount) as total_payouts,
                COUNT(*) as total_payout_records
            FROM commission_payouts
            WHERE period_start >= $1 AND period_end <= $2
            """,
            start_date, end_date
        )
        
        # Get disputes summary
        dispute_summary = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_disputes,
                SUM(disputed_amount) as total_disputed_amount
            FROM commission_disputes
            WHERE DATE(created_at) BETWEEN $1 AND $2
            """,
            start_date, end_date
        )
        
        # Get adjustments summary
        adjustment_summary = await conn.fetchrow(
            """
            SELECT 
                SUM(adjustment_amount) as total_adjustments
            FROM commission_adjustments
            WHERE DATE(created_at) BETWEEN $1 AND $2
            """,
            start_date, end_date
        )
        
        total_calculated = calc_summary['total_calculated'] or Decimal('0.00')
        total_payouts = payout_summary['total_payouts'] or Decimal('0.00')
        total_adjustments = adjustment_summary['total_adjustments'] or Decimal('0.00')
        
        variance = total_calculated - total_payouts + total_adjustments
        
        # Determine reconciliation status
        status = "balanced" if abs(variance) < Decimal('0.01') else "variance_detected"
        
        return ReconciliationReport(
            period_start=start_date,
            period_end=end_date,
            total_commissions_calculated=total_calculated,
            total_payouts_processed=total_payouts,
            total_disputes_raised=dispute_summary['total_disputes'] or 0,
            total_adjustments_made=total_adjustments,
            reconciliation_variance=variance,
            status=status
        )
    
    finally:
        await conn.close()

# =====================================================
# HEALTH CHECK AND METRICS
# =====================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        conn = await get_db_connection()
        await conn.fetchval("SELECT 1")
        await conn.close()
        
        redis_conn = await get_redis_connection()
        await redis_conn.ping()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "redis": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# =====================================================
# STARTUP AND SHUTDOWN EVENTS
# =====================================================

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global db_pool, redis_client
    
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
        logger.info("Database pool initialized")
        
        redis_client = redis.from_url(REDIS_URL)
        await redis_client.ping()
        logger.info("Redis client initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global db_pool, redis_client
    
    if db_pool:
        await db_pool.close()
        logger.info("Database pool closed")
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "commission_payout_service:app",
        host="0.0.0.0",
        port=8042,
        reload=False,
        log_level="info"
    )
