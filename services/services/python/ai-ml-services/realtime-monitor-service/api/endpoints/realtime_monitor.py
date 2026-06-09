"""
Real-time Monitor REST API Endpoints
Nigerian Remittance Platform
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import math

from db.session import get_db
from core.auth import get_current_user
from services.realtime_monitor_service import RealtimeMonitorService
from schemas.dashboard import (
    DashboardMetrics,
    TransactionSchema,
    PaginatedTransactionResponse,
    AlertSchema,
    PaginatedAlertResponse,
    SystemHealth,
    DashboardFilters,
    ApiResponse
)
from models.transaction import TransactionStatus, TransactionType
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/realtime-monitor", tags=["realtime-monitor"])


@router.get("/health", response_model=SystemHealth)
async def get_system_health(db: Session = Depends(get_db)):
    """
    Get system health status
    
    Returns:
    - System health metrics including database, Redis, and WebSocket status
    """
    from websocket.connection_manager import manager
    import time
    
    # Check database
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check Redis (simplified - in production, actually check Redis)
    redis_status = "healthy"
    
    # Get WebSocket connections
    ws_connections = manager.get_connection_count()
    
    # Calculate uptime (simplified - in production, track actual start time)
    uptime_seconds = 3600.0  # Mock value
    
    return SystemHealth(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        redis=redis_status,
        websocket_connections=ws_connections,
        uptime_seconds=uptime_seconds
    )


@router.get("/stats", response_model=DashboardMetrics)
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics and metrics
    
    Returns:
    - Active transactions count
    - Total volume (24h)
    - Success rate
    - Average processing time
    - Failed transactions count
    - Pending transactions count
    - Transactions per minute
    - Active users
    - Total fees collected
    - Currency breakdown
    - Hourly volume
    - Top corridors
    """
    service = RealtimeMonitorService(db)
    return service.get_dashboard_metrics()


@router.get("", response_model=PaginatedTransactionResponse)
async def get_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[List[TransactionStatus]] = Query(None, description="Filter by status"),
    type: Optional[List[TransactionType]] = Query(None, description="Filter by type"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    currency: Optional[List[str]] = Query(None, description="Filter by currency"),
    min_amount: Optional[float] = Query(None, description="Minimum amount"),
    max_amount: Optional[float] = Query(None, description="Maximum amount"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of transactions with filters
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - status: Filter by transaction status (can be multiple)
    - type: Filter by transaction type (can be multiple)
    - date_from: Filter transactions from this date
    - date_to: Filter transactions to this date
    - currency: Filter by currency (can be multiple)
    - min_amount: Minimum transaction amount
    - max_amount: Maximum transaction amount
    
    Returns:
    - Paginated list of transactions
    """
    service = RealtimeMonitorService(db)
    
    # Build filters
    filters = DashboardFilters(
        status=status,
        type=type,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
        min_amount=min_amount,
        max_amount=max_amount
    )
    
    # Get transactions
    transactions, total = service.get_transactions(filters, page, page_size)
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return PaginatedTransactionResponse(
        data=[TransactionSchema.from_orm(txn) for txn in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/active", response_model=PaginatedTransactionResponse)
async def get_active_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get active (pending or processing) transactions
    
    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    
    Returns:
    - Paginated list of active transactions
    """
    service = RealtimeMonitorService(db)
    transactions, total = service.get_active_transactions(page, page_size)
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return PaginatedTransactionResponse(
        data=[TransactionSchema.from_orm(txn) for txn in transactions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{transaction_id}", response_model=TransactionSchema)
async def get_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transaction by ID
    
    Path Parameters:
    - transaction_id: Transaction ID
    
    Returns:
    - Transaction details
    """
    service = RealtimeMonitorService(db)
    transaction = service.get_transaction_by_id(transaction_id)
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return TransactionSchema.from_orm(transaction)


@router.get("/alerts", response_model=PaginatedAlertResponse)
async def get_alerts(
    acknowledged: bool = Query(False, description="Filter by acknowledged status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get alerts
    
    Query Parameters:
    - acknowledged: Filter by acknowledged status (default: false)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    
    Returns:
    - Paginated list of alerts
    """
    service = RealtimeMonitorService(db)
    alerts, total = service.get_alerts(acknowledged, page, page_size)
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return PaginatedAlertResponse(
        data=[AlertSchema.from_orm(alert) for alert in alerts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.put("/alerts/{alert_id}/acknowledge", response_model=AlertSchema)
async def acknowledge_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Acknowledge an alert
    
    Path Parameters:
    - alert_id: Alert ID
    
    Returns:
    - Updated alert
    """
    service = RealtimeMonitorService(db)
    user_id = current_user.get("user_id")
    
    alert = service.acknowledge_alert(alert_id, user_id)
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return AlertSchema.from_orm(alert)


@router.get("/export/csv")
async def export_transactions_csv(
    status: Optional[List[TransactionStatus]] = Query(None),
    type: Optional[List[TransactionType]] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    currency: Optional[List[str]] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export transactions to CSV
    
    Query Parameters:
    - Same filters as get_transactions endpoint
    
    Returns:
    - CSV file
    """
    service = RealtimeMonitorService(db)
    
    # Build filters
    filters = DashboardFilters(
        status=status,
        type=type,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
        min_amount=min_amount,
        max_amount=max_amount
    )
    
    # Generate CSV
    csv_content = service.export_transactions_csv(filters)
    
    # Return as downloadable file
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=transactions_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )
