from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from service import (
    create_metric, get_metric, get_metrics, update_metric, delete_metric,
    create_task, get_task, get_tasks, update_task, delete_task,
    NotFoundError, IntegrityConstraintError
)
from schemas import (
    PerformanceMetric, PerformanceMetricCreate, PerformanceMetricUpdate,
    OptimizationTask, OptimizationTaskCreate, OptimizationTaskUpdate,
    TaskStatus
)

router = APIRouter(
    prefix="/api/v1",
    tags=["performance-optimization"],
    responses={404: {"description": "Not found"}},
)

# --- Exception Handlers for Router ---

def handle_not_found(e: NotFoundError) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(e)
    )

def handle_integrity_error(e: IntegrityConstraintError) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e)
    )

# --- PerformanceMetric Endpoints ---

@router.post(
    "/metrics/", 
    response_model=PerformanceMetric, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new performance metric"
)
def create_performance_metric(
    metric: PerformanceMetricCreate, 
    db: Session = Depends(get_db)
) -> None:
    try:
        return create_metric(db=db, metric=metric)
    except IntegrityConstraintError as e:
        handle_integrity_error(e)

@router.get(
    "/metrics/", 
    response_model=List[PerformanceMetric],
    summary="List all performance metrics"
)
def read_performance_metrics(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000), 
    db: Session = Depends(get_db)
) -> None:
    return get_metrics(db, skip=skip, limit=limit)

@router.get(
    "/metrics/{metric_id}", 
    response_model=PerformanceMetric,
    summary="Get a single performance metric by ID"
)
def read_performance_metric(
    metric_id: int, 
    db: Session = Depends(get_db)
) -> None:
    try:
        return get_metric(db, metric_id=metric_id)
    except NotFoundError as e:
        handle_not_found(e)

@router.put(
    "/metrics/{metric_id}", 
    response_model=PerformanceMetric,
    summary="Update an existing performance metric"
)
def update_performance_metric_endpoint(
    metric_id: int, 
    metric: PerformanceMetricUpdate, 
    db: Session = Depends(get_db)
) -> None:
    try:
        return update_metric(db, metric_id=metric_id, metric_update=metric)
    except NotFoundError as e:
        handle_not_found(e)
    except IntegrityConstraintError as e:
        handle_integrity_error(e)

@router.delete(
    "/metrics/{metric_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a performance metric"
)
def delete_performance_metric_endpoint(
    metric_id: int, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        delete_metric(db, metric_id=metric_id)
        return {"ok": True}
    except NotFoundError as e:
        handle_not_found(e)

# --- OptimizationTask Endpoints ---

@router.post(
    "/tasks/", 
    response_model=OptimizationTask, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new optimization task"
)
def create_optimization_task(
    task: OptimizationTaskCreate, 
    db: Session = Depends(get_db)
) -> None:
    try:
        return create_task(db=db, task=task)
    except IntegrityConstraintError as e:
        handle_integrity_error(e)

@router.get(
    "/tasks/", 
    response_model=List[OptimizationTask],
    summary="List all optimization tasks"
)
def read_optimization_tasks(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000), 
    status: Optional[TaskStatus] = Query(None, description="Filter by task status"),
    db: Session = Depends(get_db)
) -> None:
    # The TaskStatus enum from schemas is a str, so we pass its value if present
    status_filter = status.value if status else None
    return get_tasks(db, skip=skip, limit=limit, status=status_filter)

@router.get(
    "/tasks/{task_id}", 
    response_model=OptimizationTask,
    summary="Get a single optimization task by ID"
)
def read_optimization_task(
    task_id: int, 
    db: Session = Depends(get_db)
) -> None:
    try:
        return get_task(db, task_id=task_id)
    except NotFoundError as e:
        handle_not_found(e)

@router.put(
    "/tasks/{task_id}", 
    response_model=OptimizationTask,
    summary="Update an existing optimization task"
)
def update_optimization_task_endpoint(
    task_id: int, 
    task: OptimizationTaskUpdate, 
    db: Session = Depends(get_db)
) -> None:
    try:
        return update_task(db, task_id=task_id, task_update=task)
    except NotFoundError as e:
        handle_not_found(e)
    except IntegrityConstraintError as e:
        handle_integrity_error(e)

@router.delete(
    "/tasks/{task_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an optimization task"
)
def delete_optimization_task_endpoint(
    task_id: int, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        delete_task(db, task_id=task_id)
        return {"ok": True}
    except NotFoundError as e:
        handle_not_found(e)
