import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Remittance Platform - Reconciliation Service
Handles multi-source financial reconciliation with TigerBeetle ledger integration
Performs automatic matching, discrepancy detection, and reconciliation reporting
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

import asyncpg
import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("reconciliation-service")
app.include_router(metrics_router)

from pydantic import BaseModel, validator, Field
import json
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Reconciliation Service",
    description="Multi-source financial reconciliation with automatic matching",
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
SETTLEMENT_SERVICE_URL = os.getenv("SETTLEMENT_SERVICE_URL", "http://localhost:8020")
TIGERBEETLE_SERVICE_URL = os.getenv("TIGERBEETLE_SERVICE_URL", "http://localhost:8028")

# Database and Redis connections
db_pool = None
redis_client = None
http_client = None

# =====================================================
# ENUMS AND CONSTANTS
# =====================================================

class ReconciliationType(str, Enum):
    COMMISSION = "commission"
    SETTLEMENT = "settlement"
    PAYMENT = "payment"
    END_OF_DAY = "end_of_day"
    MONTH_END = "month_end"
    LEDGER = "ledger"

class ReconciliationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

class DiscrepancyType(str, Enum):
    MISSING_SOURCE = "missing_source"
    MISSING_TARGET = "missing_target"
    AMOUNT_MISMATCH = "amount_mismatch"
    STATUS_MISMATCH = "status_mismatch"
    DUPLICATE = "duplicate"
    OTHER = "other"

class DiscrepancyStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    ESCALATED = "escalated"

class MatchingStrategy(str, Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    AMOUNT_BASED = "amount_based"
    TIME_BASED = "time_based"

# =====================================================
# DATA MODELS
# =====================================================

class ReconciliationBatchCreate(BaseModel):
    batch_name: str
    reconciliation_type: ReconciliationType
    reconciliation_date: date
    source_system: str
    target_system: str
    matching_strategy: MatchingStrategy = MatchingStrategy.EXACT
    tolerance_amount: Optional[Decimal] = Field(None, ge=0)
    tolerance_percentage: Optional[Decimal] = Field(None, ge=0, le=1)
    auto_resolve: bool = False
    description: Optional[str] = None

class ReconciliationBatchResponse(BaseModel):
    id: str
    batch_name: str
    batch_number: str
    reconciliation_type: str
    reconciliation_date: date
    source_system: str
    target_system: str
    matching_strategy: str
    status: str
    total_source_records: int
    total_target_records: int
    matched_records: int
    discrepancies_count: int
    total_source_amount: Decimal
    total_target_amount: Decimal
    variance_amount: Decimal
    variance_percentage: Decimal
    created_by: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    updated_at: datetime

class DiscrepancyResponse(BaseModel):
    id: str
    batch_id: str
    discrepancy_type: str
    source_record_id: Optional[str]
    target_record_id: Optional[str]
    source_amount: Optional[Decimal]
    target_amount: Optional[Decimal]
    variance_amount: Decimal
    source_data: Dict[str, Any]
    target_data: Dict[str, Any]
    status: str
    resolution_notes: Optional[str]
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime

class DiscrepancyResolveRequest(BaseModel):
    resolution_type: str  # "accept", "adjust_source", "adjust_target", "manual"
    resolution_notes: str
    resolved_by: str
    adjustment_data: Optional[Dict[str, Any]] = None

class ReconciliationReportRequest(BaseModel):
    reconciliation_type: Optional[ReconciliationType] = None
    start_date: date
    end_date: date
    include_details: bool = False

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
# RECONCILIATION ENGINE
# =====================================================

class ReconciliationEngine:
    """Reconciliation engine with multi-source matching"""
    
    def __init__(self, db_connection, redis_connection, http_client):
        self.db = db_connection
        self.redis = redis_connection
        self.http = http_client
    
    async def create_reconciliation_batch(
        self, batch_data: ReconciliationBatchCreate, created_by: str
    ) -> str:
        """Create a new reconciliation batch"""
        batch_id = str(uuid.uuid4())
        batch_number = await self._generate_batch_number(batch_data.reconciliation_type)
        
        # Insert batch into database
        await self.db.execute("""
            INSERT INTO reconciliation_batches (
                id, batch_name, batch_number, reconciliation_type, reconciliation_date,
                source_system, target_system, matching_strategy, status,
                total_source_records, total_target_records, matched_records, discrepancies_count,
                total_source_amount, total_target_amount, variance_amount, variance_percentage,
                created_by, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        """, batch_id, batch_data.batch_name, batch_number, batch_data.reconciliation_type.value,
            batch_data.reconciliation_date, batch_data.source_system, batch_data.target_system,
            batch_data.matching_strategy.value, ReconciliationStatus.PENDING,
            0, 0, 0, 0, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
            created_by, datetime.utcnow(), datetime.utcnow())
        
        logger.info(f"Created reconciliation batch {batch_id}")
        return batch_id
    
    async def process_reconciliation_batch(self, batch_id: str) -> Dict[str, Any]:
        """Process a reconciliation batch"""
        # Get batch
        batch = await self.db.fetchrow(
            "SELECT * FROM reconciliation_batches WHERE id = $1", batch_id
        )
        
        if not batch:
            raise HTTPException(status_code=404, detail="Reconciliation batch not found")
        
        # Update status to processing
        await self.db.execute("""
            UPDATE reconciliation_batches
            SET status = $1, updated_at = $2
            WHERE id = $3
        """, ReconciliationStatus.PROCESSING, datetime.utcnow(), batch_id)
        
        try:
            # Fetch source and target data
            source_records = await self._fetch_source_data(batch)
            target_records = await self._fetch_target_data(batch)
            
            logger.info(f"Fetched {len(source_records)} source and {len(target_records)} target records")
            
            # Perform matching
            matches, discrepancies = await self._perform_matching(
                source_records,
                target_records,
                batch['matching_strategy'],
                batch.get('tolerance_amount'),
                batch.get('tolerance_percentage')
            )
            
            logger.info(f"Found {len(matches)} matches and {len(discrepancies)} discrepancies")
            
            # Calculate totals
            total_source_amount = sum(r.get('amount', Decimal("0")) for r in source_records)
            total_target_amount = sum(r.get('amount', Decimal("0")) for r in target_records)
            variance_amount = total_source_amount - total_target_amount
            variance_percentage = (
                abs(variance_amount) / total_source_amount * 100
                if total_source_amount > 0 else Decimal("0")
            )
            
            # Store discrepancies
            for discrepancy in discrepancies:
                await self._store_discrepancy(batch_id, discrepancy)
            
            # Update batch with results
            status = (
                ReconciliationStatus.COMPLETED if len(discrepancies) == 0
                else ReconciliationStatus.PARTIAL
            )
            
            await self.db.execute("""
                UPDATE reconciliation_batches
                SET status = $1,
                    total_source_records = $2,
                    total_target_records = $3,
                    matched_records = $4,
                    discrepancies_count = $5,
                    total_source_amount = $6,
                    total_target_amount = $7,
                    variance_amount = $8,
                    variance_percentage = $9,
                    completed_at = $10,
                    updated_at = $11
                WHERE id = $12
            """, status, len(source_records), len(target_records), len(matches),
                len(discrepancies), total_source_amount, total_target_amount,
                variance_amount, variance_percentage, datetime.utcnow(),
                datetime.utcnow(), batch_id)
            
            logger.info(f"Completed reconciliation batch {batch_id}")
            
            return {
                'batch_id': batch_id,
                'status': status,
                'matched': len(matches),
                'discrepancies': len(discrepancies),
                'variance_amount': float(variance_amount),
                'variance_percentage': float(variance_percentage)
            }
            
        except Exception as e:
            # Update batch as failed
            await self.db.execute("""
                UPDATE reconciliation_batches
                SET status = $1, updated_at = $2
                WHERE id = $3
            """, ReconciliationStatus.FAILED, datetime.utcnow(), batch_id)
            
            logger.error(f"Failed to process reconciliation batch {batch_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")
    
    async def resolve_discrepancy(
        self, discrepancy_id: str, resolution: DiscrepancyResolveRequest
    ) -> bool:
        """Resolve a discrepancy"""
        # Get discrepancy
        discrepancy = await self.db.fetchrow(
            "SELECT * FROM reconciliation_discrepancies WHERE id = $1", discrepancy_id
        )
        
        if not discrepancy:
            raise HTTPException(status_code=404, detail="Discrepancy not found")
        
        if discrepancy['status'] == DiscrepancyStatus.RESOLVED:
            raise HTTPException(status_code=400, detail="Discrepancy already resolved")
        
        # Apply resolution based on type
        if resolution.resolution_type == "accept":
            # Accept the discrepancy as-is
            await self.db.execute("""
                UPDATE reconciliation_discrepancies
                SET status = $1, resolution_notes = $2, resolved_by = $3, resolved_at = $4
                WHERE id = $5
            """, DiscrepancyStatus.ACCEPTED, resolution.resolution_notes,
                resolution.resolved_by, datetime.utcnow(), discrepancy_id)
            
        elif resolution.resolution_type == "adjust_source":
            # Adjust source record
            await self._adjust_source_record(discrepancy, resolution.adjustment_data)
            await self.db.execute("""
                UPDATE reconciliation_discrepancies
                SET status = $1, resolution_notes = $2, resolved_by = $3, resolved_at = $4
                WHERE id = $5
            """, DiscrepancyStatus.RESOLVED, resolution.resolution_notes,
                resolution.resolved_by, datetime.utcnow(), discrepancy_id)
            
        elif resolution.resolution_type == "adjust_target":
            # Adjust target record
            await self._adjust_target_record(discrepancy, resolution.adjustment_data)
            await self.db.execute("""
                UPDATE reconciliation_discrepancies
                SET status = $1, resolution_notes = $2, resolved_by = $3, resolved_at = $4
                WHERE id = $5
            """, DiscrepancyStatus.RESOLVED, resolution.resolution_notes,
                resolution.resolved_by, datetime.utcnow(), discrepancy_id)
            
        elif resolution.resolution_type == "manual":
            # Manual resolution
            await self.db.execute("""
                UPDATE reconciliation_discrepancies
                SET status = $1, resolution_notes = $2, resolved_by = $3, resolved_at = $4
                WHERE id = $5
            """, DiscrepancyStatus.RESOLVED, resolution.resolution_notes,
                resolution.resolved_by, datetime.utcnow(), discrepancy_id)
        
        logger.info(f"Resolved discrepancy {discrepancy_id} via {resolution.resolution_type}")
        return True
    
    # =====================================================
    # HELPER METHODS
    # =====================================================
    
    async def _generate_batch_number(self, recon_type: ReconciliationType) -> str:
        """Generate unique batch number"""
        today = datetime.utcnow().strftime("%Y%m%d")
        prefix = {
            ReconciliationType.COMMISSION: "REC-COM",
            ReconciliationType.SETTLEMENT: "REC-STL",
            ReconciliationType.PAYMENT: "REC-PAY",
            ReconciliationType.END_OF_DAY: "REC-EOD",
            ReconciliationType.MONTH_END: "REC-MEM",
            ReconciliationType.LEDGER: "REC-LDG"
        }.get(recon_type, "REC")
        
        count = await self.db.fetchval("""
            SELECT COUNT(*) FROM reconciliation_batches
            WHERE batch_number LIKE $1
        """, f"{prefix}-{today}-%")
        
        return f"{prefix}-{today}-{count + 1:04d}"
    
    async def _fetch_source_data(self, batch: Dict) -> List[Dict]:
        """Fetch source data based on reconciliation type"""
        recon_type = batch['reconciliation_type']
        recon_date = batch['reconciliation_date']
        
        if recon_type == ReconciliationType.COMMISSION:
            return await self._fetch_commission_data(recon_date)
        elif recon_type == ReconciliationType.SETTLEMENT:
            return await self._fetch_settlement_data(recon_date)
        elif recon_type == ReconciliationType.PAYMENT:
            return await self._fetch_payment_data(recon_date)
        elif recon_type == ReconciliationType.LEDGER:
            return await self._fetch_ledger_data(recon_date)
        else:
            return []
    
    async def _fetch_target_data(self, batch: Dict) -> List[Dict]:
        """Fetch target data based on reconciliation type"""
        recon_type = batch['reconciliation_type']
        recon_date = batch['reconciliation_date']
        
        if recon_type == ReconciliationType.COMMISSION:
            return await self._fetch_tigerbeetle_commission_data(recon_date)
        elif recon_type == ReconciliationType.SETTLEMENT:
            return await self._fetch_tigerbeetle_settlement_data(recon_date)
        elif recon_type == ReconciliationType.PAYMENT:
            return await self._fetch_bank_statement_data(recon_date)
        elif recon_type == ReconciliationType.LEDGER:
            return await self._fetch_external_ledger_data(recon_date)
        else:
            return []
    
    async def _fetch_commission_data(self, recon_date: date) -> List[Dict]:
        """Fetch commission calculations from commission service"""
        try:
            response = await self.http.get(
                f"{COMMISSION_SERVICE_URL}/commission/calculations",
                params={
                    'date': recon_date.isoformat(),
                    'status': 'calculated'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    'id': item['calculation_id'],
                    'transaction_id': item['transaction_id'],
                    'agent_id': item['agent_id'],
                    'amount': Decimal(str(item['total_commission'])),
                    'timestamp': item['calculated_at'],
                    'metadata': item
                }
                for item in data
            ]
        except Exception as e:
            logger.error(f"Failed to fetch commission data: {str(e)}")
            return []
    
    async def _fetch_settlement_data(self, recon_date: date) -> List[Dict]:
        """Fetch settlement data from settlement service"""
        try:
            response = await self.http.get(
                f"{SETTLEMENT_SERVICE_URL}/settlement/batches",
                params={
                    'date': recon_date.isoformat(),
                    'status': 'completed'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    'id': item['id'],
                    'batch_id': item['batch_id'],
                    'agent_id': item['agent_id'],
                    'amount': Decimal(str(item['net_amount'])),
                    'timestamp': item['processed_at'],
                    'metadata': item
                }
                for batch in data
                for item in batch.get('items', [])
            ]
        except Exception as e:
            logger.error(f"Failed to fetch settlement data: {str(e)}")
            return []
    
    async def _fetch_payment_data(self, recon_date: date) -> List[Dict]:
        """Fetch payment data from database"""
        rows = await self.db.fetch("""
            SELECT id, transaction_id, agent_id, amount, created_at, metadata
            FROM payments
            WHERE DATE(created_at) = $1
        """, recon_date)
        
        return [
            {
                'id': row['id'],
                'transaction_id': row['transaction_id'],
                'agent_id': row['agent_id'],
                'amount': row['amount'],
                'timestamp': row['created_at'],
                'metadata': row['metadata']
            }
            for row in rows
        ]
    
    async def _fetch_ledger_data(self, recon_date: date) -> List[Dict]:
        """Fetch ledger data from database"""
        rows = await self.db.fetch("""
            SELECT id, account_id, amount, transaction_type, created_at, metadata
            FROM ledger_entries
            WHERE DATE(created_at) = $1
        """, recon_date)
        
        return [
            {
                'id': row['id'],
                'account_id': row['account_id'],
                'amount': row['amount'],
                'transaction_type': row['transaction_type'],
                'timestamp': row['created_at'],
                'metadata': row['metadata']
            }
            for row in rows
        ]
    
    async def _fetch_tigerbeetle_commission_data(self, recon_date: date) -> List[Dict]:
        """Fetch commission transfers from TigerBeetle"""
        try:
            response = await self.http.get(
                f"{TIGERBEETLE_SERVICE_URL}/transfers",
                params={
                    'date': recon_date.isoformat(),
                    'transaction_type': 'commission'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    'id': item['transfer_id'],
                    'transaction_id': item.get('reference_id'),
                    'agent_id': item['credit_account_id'],
                    'amount': Decimal(str(item['amount'])) / 100,  # Convert from kobo
                    'timestamp': item['timestamp'],
                    'metadata': item
                }
                for item in data
            ]
        except Exception as e:
            logger.error(f"Failed to fetch TigerBeetle commission data: {str(e)}")
            return []
    
    async def _fetch_tigerbeetle_settlement_data(self, recon_date: date) -> List[Dict]:
        """Fetch settlement transfers from TigerBeetle"""
        try:
            response = await self.http.get(
                f"{TIGERBEETLE_SERVICE_URL}/transfers",
                params={
                    'date': recon_date.isoformat(),
                    'transaction_type': 'commission_settlement'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    'id': item['transfer_id'],
                    'agent_id': item['credit_account_id'],
                    'amount': Decimal(str(item['amount'])) / 100,
                    'timestamp': item['timestamp'],
                    'metadata': item
                }
                for item in data
            ]
        except Exception as e:
            logger.error(f"Failed to fetch TigerBeetle settlement data: {str(e)}")
            return []
    
    async def _fetch_bank_statement_data(self, recon_date: date) -> List[Dict]:
        """Fetch bank statement data"""
        # Integrate with bank API or import CSV
        return []
    
    async def _fetch_external_ledger_data(self, recon_date: date) -> List[Dict]:
        """Fetch external ledger data"""
        # Integrate with external reconciliation system
        return []
    
    async def _perform_matching(
        self,
        source_records: List[Dict],
        target_records: List[Dict],
        strategy: str,
        tolerance_amount: Optional[Decimal],
        tolerance_percentage: Optional[Decimal]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Perform matching between source and target records"""
        matches = []
        discrepancies = []
        
        # Create lookup dictionaries
        source_by_id = {r['id']: r for r in source_records}
        target_by_id = {r['id']: r for r in target_records}
        
        # Track matched records
        matched_source = set()
        matched_target = set()
        
        if strategy == MatchingStrategy.EXACT:
            # Exact ID matching
            for source in source_records:
                if source['id'] in target_by_id:
                    target = target_by_id[source['id']]
                    
                    # Check amount match
                    if self._amounts_match(
                        source['amount'], target['amount'],
                        tolerance_amount, tolerance_percentage
                    ):
                        matches.append({
                            'source_id': source['id'],
                            'target_id': target['id'],
                            'amount': source['amount']
                        })
                        matched_source.add(source['id'])
                        matched_target.add(target['id'])
                    else:
                        # Amount mismatch
                        discrepancies.append({
                            'type': DiscrepancyType.AMOUNT_MISMATCH,
                            'source_record': source,
                            'target_record': target,
                            'variance': source['amount'] - target['amount']
                        })
                        matched_source.add(source['id'])
                        matched_target.add(target['id'])
        
        elif strategy == MatchingStrategy.AMOUNT_BASED:
            # Amount-based matching
            target_by_amount = defaultdict(list)
            for target in target_records:
                target_by_amount[target['amount']].append(target)
            
            for source in source_records:
                matching_targets = target_by_amount.get(source['amount'], [])
                
                if matching_targets:
                    target = matching_targets[0]
                    matches.append({
                        'source_id': source['id'],
                        'target_id': target['id'],
                        'amount': source['amount']
                    })
                    matched_source.add(source['id'])
                    matched_target.add(target['id'])
                    matching_targets.pop(0)
        
        # Find missing records
        for source in source_records:
            if source['id'] not in matched_source:
                discrepancies.append({
                    'type': DiscrepancyType.MISSING_TARGET,
                    'source_record': source,
                    'target_record': None,
                    'variance': source['amount']
                })
        
        for target in target_records:
            if target['id'] not in matched_target:
                discrepancies.append({
                    'type': DiscrepancyType.MISSING_SOURCE,
                    'source_record': None,
                    'target_record': target,
                    'variance': -target['amount']
                })
        
        return matches, discrepancies
    
    def _amounts_match(
        self,
        amount1: Decimal,
        amount2: Decimal,
        tolerance_amount: Optional[Decimal],
        tolerance_percentage: Optional[Decimal]
    ) -> bool:
        """Check if two amounts match within tolerance"""
        diff = abs(amount1 - amount2)
        
        if tolerance_amount and diff <= tolerance_amount:
            return True
        
        if tolerance_percentage:
            max_amount = max(amount1, amount2)
            if max_amount > 0:
                percentage_diff = diff / max_amount
                if percentage_diff <= tolerance_percentage:
                    return True
        
        return diff == 0
    
    async def _store_discrepancy(self, batch_id: str, discrepancy: Dict):
        """Store a discrepancy in the database"""
        discrepancy_id = str(uuid.uuid4())
        
        source_record = discrepancy.get('source_record')
        target_record = discrepancy.get('target_record')
        
        await self.db.execute("""
            INSERT INTO reconciliation_discrepancies (
                id, batch_id, discrepancy_type,
                source_record_id, target_record_id,
                source_amount, target_amount, variance_amount,
                source_data, target_data, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, discrepancy_id, batch_id, discrepancy['type'].value,
            source_record['id'] if source_record else None,
            target_record['id'] if target_record else None,
            source_record['amount'] if source_record else None,
            target_record['amount'] if target_record else None,
            discrepancy['variance'],
            json.dumps(source_record) if source_record else None,
            json.dumps(target_record) if target_record else None,
            DiscrepancyStatus.OPEN, datetime.utcnow())
    
    async def _adjust_source_record(self, discrepancy: Dict, adjustment_data: Dict):
        """Adjust source record to match target"""
        # Implementation depends on source system
        logger.info(f"Adjusting source record for discrepancy {discrepancy['id']}")
    
    async def _adjust_target_record(self, discrepancy: Dict, adjustment_data: Dict):
        """Adjust target record to match source"""
        # Implementation depends on target system
        logger.info(f"Adjusting target record for discrepancy {discrepancy['id']}")

# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/reconciliation/batches", response_model=ReconciliationBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_reconciliation_batch(
    batch_data: ReconciliationBatchCreate,
    created_by: str = "system"
):
    """Create a new reconciliation batch"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = ReconciliationEngine(conn, redis_conn, http)
        batch_id = await engine.create_reconciliation_batch(batch_data, created_by)
        
        # Fetch created batch
        batch = await conn.fetchrow("SELECT * FROM reconciliation_batches WHERE id = $1", batch_id)
        
        return dict(batch)
    finally:
        await release_db_connection(conn)

@app.get("/reconciliation/batches", response_model=List[ReconciliationBatchResponse])
async def list_reconciliation_batches(
    reconciliation_type: Optional[ReconciliationType] = None,
    status_filter: Optional[ReconciliationStatus] = None,
    limit: int = Query(50, ge=1, le=100)
):
    """List reconciliation batches"""
    conn = await get_db_connection()
    try:
        query = "SELECT * FROM reconciliation_batches WHERE 1=1"
        params = []
        
        if reconciliation_type:
            params.append(reconciliation_type.value)
            query += f" AND reconciliation_type = ${len(params)}"
        
        if status_filter:
            params.append(status_filter.value)
            query += f" AND status = ${len(params)}"
        
        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        batches = await conn.fetch(query, *params)
        return [dict(batch) for batch in batches]
    finally:
        await release_db_connection(conn)

@app.get("/reconciliation/batches/{batch_id}", response_model=ReconciliationBatchResponse)
async def get_reconciliation_batch(batch_id: str):
    """Get reconciliation batch details"""
    conn = await get_db_connection()
    try:
        batch = await conn.fetchrow("SELECT * FROM reconciliation_batches WHERE id = $1", batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Reconciliation batch not found")
        return dict(batch)
    finally:
        await release_db_connection(conn)

@app.post("/reconciliation/batches/{batch_id}/process")
async def process_reconciliation_batch(batch_id: str, background_tasks: BackgroundTasks):
    """Process a reconciliation batch"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = ReconciliationEngine(conn, redis_conn, http)
        
        # Process in background
        background_tasks.add_task(engine.process_reconciliation_batch, batch_id)
        
        return {
            'batch_id': batch_id,
            'message': 'Reconciliation processing started',
            'status': 'processing'
        }
    finally:
        await release_db_connection(conn)

@app.get("/reconciliation/batches/{batch_id}/discrepancies", response_model=List[DiscrepancyResponse])
async def get_batch_discrepancies(batch_id: str):
    """Get discrepancies for a reconciliation batch"""
    conn = await get_db_connection()
    try:
        discrepancies = await conn.fetch("""
            SELECT * FROM reconciliation_discrepancies
            WHERE batch_id = $1
            ORDER BY created_at
        """, batch_id)
        
        return [dict(d) for d in discrepancies]
    finally:
        await release_db_connection(conn)

@app.post("/reconciliation/discrepancies/{discrepancy_id}/resolve")
async def resolve_discrepancy(discrepancy_id: str, resolution: DiscrepancyResolveRequest):
    """Resolve a discrepancy"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        engine = ReconciliationEngine(conn, redis_conn, http)
        result = await engine.resolve_discrepancy(discrepancy_id, resolution)
        
        return {
            'discrepancy_id': discrepancy_id,
            'resolved': result,
            'message': 'Discrepancy resolved successfully'
        }
    finally:
        await release_db_connection(conn)

@app.get("/reconciliation/discrepancies")
async def list_discrepancies(
    status_filter: Optional[DiscrepancyStatus] = None,
    discrepancy_type: Optional[DiscrepancyType] = None,
    limit: int = Query(100, ge=1, le=500)
):
    """List discrepancies"""
    conn = await get_db_connection()
    try:
        query = "SELECT * FROM reconciliation_discrepancies WHERE 1=1"
        params = []
        
        if status_filter:
            params.append(status_filter.value)
            query += f" AND status = ${len(params)}"
        
        if discrepancy_type:
            params.append(discrepancy_type.value)
            query += f" AND discrepancy_type = ${len(params)}"
        
        query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        discrepancies = await conn.fetch(query, *params)
        return [dict(d) for d in discrepancies]
    finally:
        await release_db_connection(conn)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "reconciliation-service",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    conn = await get_db_connection()
    try:
        total_batches = await conn.fetchval("SELECT COUNT(*) FROM reconciliation_batches")
        open_discrepancies = await conn.fetchval(
            "SELECT COUNT(*) FROM reconciliation_discrepancies WHERE status = $1",
            DiscrepancyStatus.OPEN
        )
        
        return {
            'total_batches': total_batches or 0,
            'open_discrepancies': open_discrepancies or 0,
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
    logger.info("Starting Reconciliation Service...")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    redis_client = redis.from_url(REDIS_URL)
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Reconciliation Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    global db_pool, redis_client, http_client
    logger.info("Shutting down Reconciliation Service...")
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()
    logger.info("Reconciliation Service shut down successfully")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8021))
    uvicorn.run(app, host="0.0.0.0", port=port)

