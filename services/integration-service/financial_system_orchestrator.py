import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Remittance Platform - Financial System Orchestrator
Integrates Commission, Settlement, Reconciliation, and TigerBeetle services
Provides end-to-end financial workflows
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from decimal import Decimal
from enum import Enum

import asyncpg
import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("financial-system-orchestrator")
app.include_router(metrics_router)

from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Financial System Orchestrator",
    description="End-to-end integration of commission, settlement, and reconciliation",
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
COMMISSION_SERVICE_URL = os.getenv("COMMISSION_SERVICE_URL", "http://localhost:8010")
SETTLEMENT_SERVICE_URL = os.getenv("SETTLEMENT_SERVICE_URL", "http://localhost:8020")
RECONCILIATION_SERVICE_URL = os.getenv("RECONCILIATION_SERVICE_URL", "http://localhost:8021")
TIGERBEETLE_SERVICE_URL = os.getenv("TIGERBEETLE_SERVICE_URL", "http://localhost:8028")
HIERARCHY_SERVICE_URL = os.getenv("HIERARCHY_SERVICE_URL", "http://localhost:8015")

# Database and Redis connections
db_pool = None
redis_client = None
http_client = None

# =====================================================
# DATA MODELS
# =====================================================

class EndOfDayRequest(BaseModel):
    processing_date: date
    auto_settle: bool = False
    auto_reconcile: bool = True
    settlement_threshold: Optional[Decimal] = Field(None, ge=0)

class MonthEndRequest(BaseModel):
    year: int
    month: int
    auto_settle: bool = True
    auto_reconcile: bool = True
    generate_reports: bool = True

class CommissionCalculationRequest(BaseModel):
    transaction_id: str
    agent_id: str
    transaction_amount: Decimal
    product_type: str
    calculate_hierarchy: bool = True

class WorkflowStatus(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str
    steps_completed: List[str]
    steps_pending: List[str]
    errors: List[str]
    created_at: datetime
    completed_at: Optional[datetime]

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
        http_client = httpx.AsyncClient(timeout=60.0)
    return http_client

# =====================================================
# FINANCIAL SYSTEM ORCHESTRATOR
# =====================================================

class FinancialOrchestrator:
    """Orchestrates end-to-end financial workflows"""
    
    def __init__(self, db_connection, redis_connection, http_client):
        self.db = db_connection
        self.redis = redis_connection
        self.http = http_client
    
    async def process_transaction_with_commission(
        self, transaction_id: str, agent_id: str, amount: Decimal, product_type: str
    ) -> Dict[str, Any]:
        """
        Complete transaction processing workflow:
        1. Calculate commission (with hierarchy)
        2. Record in TigerBeetle ledger
        3. Update agent balances
        """
        workflow_id = str(uuid.uuid4())
        results = {
            'workflow_id': workflow_id,
            'transaction_id': transaction_id,
            'steps': []
        }
        
        try:
            # Step 1: Calculate commission
            logger.info(f"[{workflow_id}] Calculating commission for transaction {transaction_id}")
            commission_response = await self.http.post(
                f"{COMMISSION_SERVICE_URL}/commission/calculate",
                json={
                    'transaction_id': transaction_id,
                    'agent_id': agent_id,
                    'transaction_amount': float(amount),
                    'product_type': product_type
                }
            )
            commission_response.raise_for_status()
            commission_data = commission_response.json()
            results['steps'].append({
                'step': 'commission_calculation',
                'status': 'completed',
                'data': commission_data
            })
            
            # Step 2: Record commission in TigerBeetle
            logger.info(f"[{workflow_id}] Recording commission in TigerBeetle")
            total_commission = Decimal(str(commission_data['total_commission']))
            
            tigerbeetle_response = await self.http.post(
                f"{TIGERBEETLE_SERVICE_URL}/transfer",
                json={
                    'from_user_id': 'platform_revenue',
                    'to_user_id': agent_id,
                    'amount': float(total_commission),
                    'transaction_type': 'commission',
                    'description': f"Commission for transaction {transaction_id}",
                    'metadata': {
                        'transaction_id': transaction_id,
                        'workflow_id': workflow_id,
                        'commission_calculation_id': commission_data['calculation_id']
                    }
                }
            )
            tigerbeetle_response.raise_for_status()
            tigerbeetle_data = tigerbeetle_response.json()
            results['steps'].append({
                'step': 'tigerbeetle_transfer',
                'status': 'completed',
                'data': tigerbeetle_data
            })
            
            # Step 3: Process hierarchy commissions
            if commission_data.get('hierarchy_commissions'):
                logger.info(f"[{workflow_id}] Processing hierarchy commissions")
                for hier_comm in commission_data['hierarchy_commissions']:
                    hier_response = await self.http.post(
                        f"{TIGERBEETLE_SERVICE_URL}/transfer",
                        json={
                            'from_user_id': 'platform_revenue',
                            'to_user_id': hier_comm['agent_id'],
                            'amount': float(hier_comm['commission_amount']),
                            'transaction_type': 'commission',
                            'description': f"Hierarchy commission for transaction {transaction_id}",
                            'metadata': {
                                'transaction_id': transaction_id,
                                'workflow_id': workflow_id,
                                'parent_agent_id': agent_id,
                                'level': hier_comm['level']
                            }
                        }
                    )
                    hier_response.raise_for_status()
                
                results['steps'].append({
                    'step': 'hierarchy_commissions',
                    'status': 'completed',
                    'count': len(commission_data['hierarchy_commissions'])
                })
            
            results['status'] = 'completed'
            results['total_commission'] = float(total_commission)
            
            logger.info(f"[{workflow_id}] Transaction processing completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"[{workflow_id}] Transaction processing failed: {str(e)}")
            results['status'] = 'failed'
            results['error'] = str(e)
            return results
    
    async def end_of_day_processing(
        self, processing_date: date, auto_settle: bool = False, auto_reconcile: bool = True
    ) -> Dict[str, Any]:
        """
        End-of-day processing workflow:
        1. Reconcile all commissions with TigerBeetle
        2. Optionally create settlement batch
        3. Generate EOD reports
        """
        workflow_id = str(uuid.uuid4())
        results = {
            'workflow_id': workflow_id,
            'processing_date': processing_date.isoformat(),
            'steps': []
        }
        
        try:
            # Step 1: Reconcile commissions
            if auto_reconcile:
                logger.info(f"[{workflow_id}] Starting commission reconciliation for {processing_date}")
                recon_response = await self.http.post(
                    f"{RECONCILIATION_SERVICE_URL}/reconciliation/batches",
                    json={
                        'batch_name': f"EOD Commission Reconciliation - {processing_date}",
                        'reconciliation_type': 'commission',
                        'reconciliation_date': processing_date.isoformat(),
                        'source_system': 'commission_service',
                        'target_system': 'tigerbeetle',
                        'matching_strategy': 'exact',
                        'auto_resolve': False
                    }
                )
                recon_response.raise_for_status()
                recon_data = recon_response.json()
                
                # Process reconciliation
                process_response = await self.http.post(
                    f"{RECONCILIATION_SERVICE_URL}/reconciliation/batches/{recon_data['id']}/process"
                )
                process_response.raise_for_status()
                
                results['steps'].append({
                    'step': 'commission_reconciliation',
                    'status': 'completed',
                    'batch_id': recon_data['id']
                })
            
            # Step 2: Create settlement batch
            if auto_settle:
                logger.info(f"[{workflow_id}] Creating settlement batch for {processing_date}")
                settlement_response = await self.http.post(
                    f"{SETTLEMENT_SERVICE_URL}/settlement/batches",
                    json={
                        'batch_name': f"EOD Settlement - {processing_date}",
                        'settlement_period_start': processing_date.isoformat(),
                        'settlement_period_end': processing_date.isoformat(),
                        'auto_process': False
                    }
                )
                settlement_response.raise_for_status()
                settlement_data = settlement_response.json()
                
                results['steps'].append({
                    'step': 'settlement_batch_creation',
                    'status': 'completed',
                    'batch_id': settlement_data['id'],
                    'total_amount': float(settlement_data['total_amount'])
                })
            
            # Step 3: Generate EOD summary
            summary = await self._generate_eod_summary(processing_date)
            results['steps'].append({
                'step': 'eod_summary',
                'status': 'completed',
                'data': summary
            })
            
            results['status'] = 'completed'
            logger.info(f"[{workflow_id}] EOD processing completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"[{workflow_id}] EOD processing failed: {str(e)}")
            results['status'] = 'failed'
            results['error'] = str(e)
            return results
    
    async def month_end_processing(
        self, year: int, month: int, auto_settle: bool = True, auto_reconcile: bool = True
    ) -> Dict[str, Any]:
        """
        Month-end processing workflow:
        1. Reconcile entire month
        2. Create monthly settlement batch
        3. Generate monthly reports
        4. Archive data
        """
        workflow_id = str(uuid.uuid4())
        period_start = date(year, month, 1)
        
        # Calculate last day of month
        if month == 12:
            period_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)
        
        results = {
            'workflow_id': workflow_id,
            'period': f"{year}-{month:02d}",
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'steps': []
        }
        
        try:
            # Step 1: Monthly reconciliation
            if auto_reconcile:
                logger.info(f"[{workflow_id}] Starting monthly reconciliation for {year}-{month:02d}")
                
                # Reconcile commissions
                comm_recon_response = await self.http.post(
                    f"{RECONCILIATION_SERVICE_URL}/reconciliation/batches",
                    json={
                        'batch_name': f"Month-End Commission Reconciliation - {year}-{month:02d}",
                        'reconciliation_type': 'commission',
                        'reconciliation_date': period_end.isoformat(),
                        'source_system': 'commission_service',
                        'target_system': 'tigerbeetle',
                        'matching_strategy': 'exact'
                    }
                )
                comm_recon_response.raise_for_status()
                comm_recon_data = comm_recon_response.json()
                
                # Process reconciliation
                await self.http.post(
                    f"{RECONCILIATION_SERVICE_URL}/reconciliation/batches/{comm_recon_data['id']}/process"
                )
                
                results['steps'].append({
                    'step': 'monthly_commission_reconciliation',
                    'status': 'completed',
                    'batch_id': comm_recon_data['id']
                })
            
            # Step 2: Monthly settlement
            if auto_settle:
                logger.info(f"[{workflow_id}] Creating monthly settlement batch")
                settlement_response = await self.http.post(
                    f"{SETTLEMENT_SERVICE_URL}/settlement/batches",
                    json={
                        'batch_name': f"Monthly Settlement - {year}-{month:02d}",
                        'settlement_period_start': period_start.isoformat(),
                        'settlement_period_end': period_end.isoformat(),
                        'auto_process': False
                    }
                )
                settlement_response.raise_for_status()
                settlement_data = settlement_response.json()
                
                results['steps'].append({
                    'step': 'monthly_settlement',
                    'status': 'completed',
                    'batch_id': settlement_data['id'],
                    'total_agents': settlement_data['total_agents'],
                    'total_amount': float(settlement_data['total_amount'])
                })
            
            # Step 3: Generate monthly reports
            monthly_summary = await self._generate_monthly_summary(year, month)
            results['steps'].append({
                'step': 'monthly_reports',
                'status': 'completed',
                'data': monthly_summary
            })
            
            results['status'] = 'completed'
            logger.info(f"[{workflow_id}] Month-end processing completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"[{workflow_id}] Month-end processing failed: {str(e)}")
            results['status'] = 'failed'
            results['error'] = str(e)
            return results
    
    async def _generate_eod_summary(self, processing_date: date) -> Dict[str, Any]:
        """Generate end-of-day summary"""
        summary = {
            'date': processing_date.isoformat(),
            'transactions': {},
            'commissions': {},
            'settlements': {}
        }
        
        # Get transaction count and volume
        trans_stats = await self.db.fetchrow("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total_amount
            FROM transactions
            WHERE DATE(created_at) = $1
        """, processing_date)
        
        summary['transactions'] = {
            'count': trans_stats['count'] or 0,
            'total_amount': float(trans_stats['total_amount'] or 0)
        }
        
        # Get commission stats
        comm_stats = await self.db.fetchrow("""
            SELECT COUNT(*) as count, COALESCE(SUM(total_commission), 0) as total_commission
            FROM commission_calculations
            WHERE DATE(calculated_at) = $1
        """, processing_date)
        
        summary['commissions'] = {
            'count': comm_stats['count'] or 0,
            'total_amount': float(comm_stats['total_commission'] or 0)
        }
        
        return summary
    
    async def _generate_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Generate monthly summary"""
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)
        
        summary = {
            'year': year,
            'month': month,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'transactions': {},
            'commissions': {},
            'settlements': {},
            'top_agents': []
        }
        
        # Get monthly transaction stats
        trans_stats = await self.db.fetchrow("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total_amount
            FROM transactions
            WHERE DATE(created_at) >= $1 AND DATE(created_at) <= $2
        """, period_start, period_end)
        
        summary['transactions'] = {
            'count': trans_stats['count'] or 0,
            'total_amount': float(trans_stats['total_amount'] or 0)
        }
        
        # Get monthly commission stats
        comm_stats = await self.db.fetchrow("""
            SELECT COUNT(*) as count, COALESCE(SUM(total_commission), 0) as total_commission
            FROM commission_calculations
            WHERE DATE(calculated_at) >= $1 AND DATE(calculated_at) <= $2
        """, period_start, period_end)
        
        summary['commissions'] = {
            'count': comm_stats['count'] or 0,
            'total_amount': float(comm_stats['total_commission'] or 0)
        }
        
        # Get top agents by commission
        top_agents = await self.db.fetch("""
            SELECT agent_id, COUNT(*) as transaction_count, SUM(total_commission) as total_commission
            FROM commission_calculations
            WHERE DATE(calculated_at) >= $1 AND DATE(calculated_at) <= $2
            GROUP BY agent_id
            ORDER BY total_commission DESC
            LIMIT 10
        """, period_start, period_end)
        
        summary['top_agents'] = [
            {
                'agent_id': row['agent_id'],
                'transaction_count': row['transaction_count'],
                'total_commission': float(row['total_commission'])
            }
            for row in top_agents
        ]
        
        return summary

# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/workflows/transaction")
async def process_transaction(request: CommissionCalculationRequest):
    """Process transaction with commission calculation and ledger recording"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        orchestrator = FinancialOrchestrator(conn, redis_conn, http)
        result = await orchestrator.process_transaction_with_commission(
            request.transaction_id,
            request.agent_id,
            request.transaction_amount,
            request.product_type
        )
        return result
    finally:
        await release_db_connection(conn)

@app.post("/workflows/end-of-day")
async def end_of_day(request: EndOfDayRequest, background_tasks: BackgroundTasks):
    """Run end-of-day processing workflow"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        orchestrator = FinancialOrchestrator(conn, redis_conn, http)
        
        # Run in background
        background_tasks.add_task(
            orchestrator.end_of_day_processing,
            request.processing_date,
            request.auto_settle,
            request.auto_reconcile
        )
        
        return {
            'message': 'End-of-day processing started',
            'processing_date': request.processing_date.isoformat(),
            'status': 'processing'
        }
    finally:
        await release_db_connection(conn)

@app.post("/workflows/month-end")
async def month_end(request: MonthEndRequest, background_tasks: BackgroundTasks):
    """Run month-end processing workflow"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    http = await get_http_client()
    
    try:
        orchestrator = FinancialOrchestrator(conn, redis_conn, http)
        
        # Run in background
        background_tasks.add_task(
            orchestrator.month_end_processing,
            request.year,
            request.month,
            request.auto_settle,
            request.auto_reconcile
        )
        
        return {
            'message': 'Month-end processing started',
            'period': f"{request.year}-{request.month:02d}",
            'status': 'processing'
        }
    finally:
        await release_db_connection(conn)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "financial-system-orchestrator",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/services/status")
async def check_services_status():
    """Check status of all integrated services"""
    http = await get_http_client()
    services = {
        'commission': COMMISSION_SERVICE_URL,
        'settlement': SETTLEMENT_SERVICE_URL,
        'reconciliation': RECONCILIATION_SERVICE_URL,
        'tigerbeetle': TIGERBEETLE_SERVICE_URL,
        'hierarchy': HIERARCHY_SERVICE_URL
    }
    
    status_results = {}
    
    for service_name, service_url in services.items():
        try:
            response = await http.get(f"{service_url}/health", timeout=5.0)
            status_results[service_name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'url': service_url
            }
        except Exception as e:
            status_results[service_name] = {
                'status': 'unreachable',
                'url': service_url,
                'error': str(e)
            }
    
    all_healthy = all(s['status'] == 'healthy' for s in status_results.values())
    
    return {
        'overall_status': 'healthy' if all_healthy else 'degraded',
        'services': status_results,
        'timestamp': datetime.utcnow().isoformat()
    }

# =====================================================
# STARTUP AND SHUTDOWN
# =====================================================

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global db_pool, redis_client, http_client
    logger.info("Starting Financial System Orchestrator...")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    redis_client = redis.from_url(REDIS_URL)
    http_client = httpx.AsyncClient(timeout=60.0)
    logger.info("Financial System Orchestrator started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    global db_pool, redis_client, http_client
    logger.info("Shutting down Financial System Orchestrator...")
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()
    logger.info("Financial System Orchestrator shut down successfully")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8025))
    uvicorn.run(app, host="0.0.0.0", port=port)

