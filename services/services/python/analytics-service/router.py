import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, desc

from . import models
from .config import get_db, settings
from .models import (
    ActivityLog, ActivityLogCreate, ActivityLogResponse,
    ServiceMetric, ServiceMetricCreate, ServiceMetricResponse, ServiceMetricUpdate,
    PaginatedResponse
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=settings.API_V1_STR,
    tags=["analytics-service"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_metric_by_id(db: Session, metric_id: UUID) -> ServiceMetric:
    """Fetches a ServiceMetric by its ID or raises a 404 error."""
    metric = db.query(ServiceMetric).filter(ServiceMetric.id == metric_id).first()
    if not metric:
        raise HTTPException(status_code=404, detail=f"ServiceMetric with ID {metric_id} not found")
    return metric

# --- ServiceMetric CRUD Endpoints ---

@router.post("/metrics", response_model=ServiceMetricResponse, status_code=201, summary="Create a new service metric")
def create_metric(metric_in: ServiceMetricCreate, db: Session = Depends(get_db)):
    """
    Records a new analytical metric for a service.
    
    This endpoint is typically used by other services to report their performance,
    usage, or business-related metrics.
    """
    logger.info(f"Creating new metric: {metric_in.metric_name} for service: {metric_in.service_name}")
    
    # Convert Pydantic model to SQLAlchemy model
    db_metric = ServiceMetric(**metric_in.dict(exclude_none=True))
    
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    
    # Log the activity
    db_log = ActivityLog(
        user_id=metric_in.source_id,
        action="CREATE_METRIC",
        resource_type="ServiceMetric",
        resource_id=str(db_metric.id),
        details=f"Metric {db_metric.metric_name} recorded by {db_metric.service_name}"
    )
    db.add(db_log)
    db.commit()
    
    return db_metric

@router.get("/metrics/{metric_id}", response_model=ServiceMetricResponse, summary="Get a service metric by ID")
def read_metric(metric_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single service metric record using its unique ID.
    """
    return get_metric_by_id(db, metric_id)

@router.get("/metrics", response_model=PaginatedResponse, summary="List all service metrics with filtering and pagination")
def list_metrics(
    db: Session = Depends(get_db),
    service_name: Optional[str] = Query(None, description="Filter by the name of the service."),
    metric_name: Optional[str] = Query(None, description="Filter by the specific metric name."),
    page: int = Query(1, ge=1, description="Page number."),
    size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Number of items per page."),
):
    """
    Lists service metrics, allowing for filtering by service and metric name,
    and supports pagination.
    """
    query = db.query(ServiceMetric)
    
    if service_name:
        query = query.filter(ServiceMetric.service_name == service_name)
    if metric_name:
        query = query.filter(ServiceMetric.metric_name == metric_name)
        
    total = query.count()
    
    metrics = query.order_by(desc(ServiceMetric.timestamp)).offset((page - 1) * size).limit(size).all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        size=size,
        items=[ServiceMetricResponse.from_orm(m) for m in metrics]
    )

@router.patch("/metrics/{metric_id}", response_model=ServiceMetricResponse, summary="Update an existing service metric")
def update_metric(metric_id: UUID, metric_in: ServiceMetricUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing service metric record. Only provided fields will be modified.
    Note: Metrics are typically immutable, so this endpoint is provided for administrative
    or correction purposes only.
    """
    db_metric = get_metric_by_id(db, metric_id)
    
    update_data = metric_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_metric, key, value)
        
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    
    # Log the activity
    db_log = ActivityLog(
        action="UPDATE_METRIC",
        resource_type="ServiceMetric",
        resource_id=str(db_metric.id),
        details=f"Metric {db_metric.metric_name} updated."
    )
    db.add(db_log)
    db.commit()
    
    return db_metric

@router.delete("/metrics/{metric_id}", status_code=204, summary="Delete a service metric")
def delete_metric(metric_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a service metric record.
    Note: Deletion of analytical data should be handled with caution.
    """
    db_metric = get_metric_by_id(db, metric_id)
    
    db.delete(db_metric)
    db.commit()
    
    # Log the activity
    db_log = ActivityLog(
        action="DELETE_METRIC",
        resource_type="ServiceMetric",
        resource_id=str(metric_id),
        details=f"Metric with ID {metric_id} deleted."
    )
    db.add(db_log)
    db.commit()
    
    return {"ok": True}

# --- Business-Specific Endpoints (Aggregation) ---

@router.get("/metrics/aggregate", summary="Get aggregated metric data", response_model=List[dict])
def get_aggregated_metrics(
    db: Session = Depends(get_db),
    metric_name: str = Query(..., description="The specific metric name to aggregate."),
    aggregation_func: str = Query("avg", description="The aggregation function (e.g., 'avg', 'sum', 'count', 'min', 'max')."),
    group_by: str = Query("day", description="The time unit to group by ('hour', 'day', 'month', 'year')."),
    service_name: Optional[str] = Query(None, description="Filter by the name of the service."),
):
    """
    Calculates aggregated statistics for a specific metric over time.
    
    The `group_by` parameter determines the time resolution of the aggregation.
    """
    
    if aggregation_func.lower() not in ["avg", "sum", "count", "min", "max"]:
        raise HTTPException(status_code=400, detail="Invalid aggregation_func. Must be one of: avg, sum, count, min, max.")
        
    if group_by.lower() not in ["hour", "day", "month", "year"]:
        raise HTTPException(status_code=400, detail="Invalid group_by. Must be one of: hour, day, month, year.")

    # Map string function name to SQLAlchemy function
    agg_map = {
        "avg": func.avg(ServiceMetric.metric_value).label("aggregated_value"),
        "sum": func.sum(ServiceMetric.metric_value).label("aggregated_value"),
        "count": func.count(ServiceMetric.metric_value).label("aggregated_value"),
        "min": func.min(ServiceMetric.metric_value).label("aggregated_value"),
        "max": func.max(ServiceMetric.metric_value).label("aggregated_value"),
    }
    
    # Extract the time unit for grouping
    time_unit = extract(group_by.lower(), ServiceMetric.timestamp).label("time_unit")
    
    query = db.query(time_unit, agg_map[aggregation_func.lower()])
    
    # Filter by metric name
    query = query.filter(ServiceMetric.metric_name == metric_name)
    
    # Optional filter by service name
    if service_name:
        query = query.filter(ServiceMetric.service_name == service_name)
        
    # Group and order
    results = query.group_by(time_unit).order_by(time_unit).all()
    
    # Format the results
    formatted_results = [
        {
            "time_unit": int(result[0]),
            "aggregated_value": result[1],
            "aggregation_func": aggregation_func,
            "metric_name": metric_name,
            "group_by": group_by
        }
        for result in results
    ]
    
    return formatted_results

# --- ActivityLog Endpoints ---

@router.post("/logs", response_model=ActivityLogResponse, status_code=201, summary="Create a new activity log entry")
def create_log(log_in: ActivityLogCreate, db: Session = Depends(get_db)):
    """
    Records a new activity log entry. This is typically used internally by services
    to track user or system actions.
    """
    logger.info(f"Creating new activity log: {log_in.action} by user: {log_in.user_id}")
    
    db_log = ActivityLog(**log_in.dict(exclude_none=True))
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    return db_log

@router.get("/logs", response_model=List[ActivityLogResponse], summary="List recent activity logs")
def list_logs(
    db: Session = Depends(get_db),
    user_id: Optional[str] = Query(None, description="Filter by the ID of the user."),
    action: Optional[str] = Query(None, description="Filter by the action performed."),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Maximum number of logs to return."),
):
    """
    Retrieves a list of the most recent activity logs, with optional filtering.
    """
    query = db.query(ActivityLog)
    
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if action:
        query = query.filter(ActivityLog.action == action)
        
    logs = query.order_by(desc(ActivityLog.timestamp)).limit(limit).all()
    
    return [ActivityLogResponse.from_orm(log) for log in logs]
