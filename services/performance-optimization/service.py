from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from models import PerformanceMetric, OptimizationTask
from schemas import (
    PerformanceMetricCreate, PerformanceMetricUpdate, 
    OptimizationTaskCreate, OptimizationTaskUpdate
)
from config import logger

# --- Custom Exceptions ---

class NotFoundError(Exception):
    """Custom exception for when an item is not found in the database."""
    def __init__(self, model_name: str, item_id: int) -> None:
        self.model_name = model_name
        self.item_id = item_id
        super().__init__(f"{model_name} with ID {item_id} not found.")

class IntegrityConstraintError(Exception):
    """Custom exception for database integrity errors."""
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

# --- PerformanceMetric Service ---

def create_metric(db: Session, metric: PerformanceMetricCreate) -> PerformanceMetric:
    """Creates a new performance metric record."""
    logger.info(f"Attempting to create new metric: {metric.system_name}/{metric.metric_type}")
    try:
        db_metric = PerformanceMetric(**metric.model_dump())
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        logger.info(f"Successfully created metric with ID: {db_metric.id}")
        return db_metric
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error while creating metric: {e}")
        raise IntegrityConstraintError("Could not create metric due to a data integrity violation.")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while creating metric: {e}")
        raise

def get_metric(db: Session, metric_id: int) -> PerformanceMetric:
    """Retrieves a single performance metric by ID."""
    metric = db.query(PerformanceMetric).filter(PerformanceMetric.id == metric_id).first()
    if not metric:
        logger.warning(f"Metric with ID {metric_id} not found.")
        raise NotFoundError("PerformanceMetric", metric_id)
    return metric

def get_metrics(db: Session, skip: int = 0, limit: int = 100) -> List[PerformanceMetric]:
    """Retrieves a list of performance metrics."""
    return db.query(PerformanceMetric).offset(skip).limit(limit).all()

def update_metric(db: Session, metric_id: int, metric_update: PerformanceMetricUpdate) -> PerformanceMetric:
    """Updates an existing performance metric record."""
    db_metric = get_metric(db, metric_id) # Uses get_metric for existence check and NotFoundError
    
    logger.info(f"Attempting to update metric ID: {metric_id}")
    update_data = metric_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_metric, key, value)
    
    try:
        db.add(db_metric)
        db.commit()
        db.refresh(db_metric)
        logger.info(f"Successfully updated metric ID: {metric_id}")
        return db_metric
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error while updating metric ID {metric_id}: {e}")
        raise IntegrityConstraintError("Could not update metric due to a data integrity violation.")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while updating metric ID {metric_id}: {e}")
        raise

def delete_metric(db: Session, metric_id: int) -> PerformanceMetric:
    """Deletes a performance metric record."""
    db_metric = get_metric(db, metric_id) # Uses get_metric for existence check and NotFoundError
    
    logger.info(f"Attempting to delete metric ID: {metric_id}")
    db.delete(db_metric)
    db.commit()
    logger.info(f"Successfully deleted metric ID: {metric_id}")
    return db_metric

# --- OptimizationTask Service ---

def create_task(db: Session, task: OptimizationTaskCreate) -> OptimizationTask:
    """Creates a new optimization task."""
    logger.info(f"Attempting to create new task: {task.title}")
    try:
        db_task = OptimizationTask(**task.model_dump())
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        logger.info(f"Successfully created task with ID: {db_task.id}")
        return db_task
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error while creating task: {e}")
        raise IntegrityConstraintError("Could not create task due to a data integrity violation.")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while creating task: {e}")
        raise

def get_task(db: Session, task_id: int) -> OptimizationTask:
    """Retrieves a single optimization task by ID."""
    task = db.query(OptimizationTask).filter(OptimizationTask.id == task_id).first()
    if not task:
        logger.warning(f"Task with ID {task_id} not found.")
        raise NotFoundError("OptimizationTask", task_id)
    return task

def get_tasks(db: Session, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[OptimizationTask]:
    """Retrieves a list of optimization tasks, optionally filtered by status."""
    query = db.query(OptimizationTask)
    if status:
        # Assuming status is passed as a string matching the enum value
        query = query.filter(OptimizationTask.status == status)
    
    return query.offset(skip).limit(limit).all()

def update_task(db: Session, task_id: int, task_update: OptimizationTaskUpdate) -> OptimizationTask:
    """Updates an existing optimization task."""
    db_task = get_task(db, task_id) # Uses get_task for existence check and NotFoundError
    
    logger.info(f"Attempting to update task ID: {task_id}")
    update_data = task_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_task, key, value)
    
    try:
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        logger.info(f"Successfully updated task ID: {task_id}")
        return db_task
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error while updating task ID {task_id}: {e}")
        raise IntegrityConstraintError("Could not update task due to a data integrity violation.")
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error while updating task ID {task_id}: {e}")
        raise

def delete_task(db: Session, task_id: int) -> OptimizationTask:
    """Deletes an optimization task."""
    db_task = get_task(db, task_id) # Uses get_task for existence check and NotFoundError
    
    logger.info(f"Attempting to delete task ID: {task_id}")
    db.delete(db_task)
    db.commit()
    logger.info(f"Successfully deleted task ID: {task_id}")
    return db_task
