import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import get_db, get_settings

# Initialize logger
settings = get_settings()
logger = logging.getLogger(settings.SERVICE_NAME)

router = APIRouter(
    prefix="/tasks",
    tags=["AI Orchestration Tasks"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_task_or_404(db: Session, task_id: int) -> models.OrchestrationTask:
    """Fetches a task by ID or raises a 404 HTTP exception."""
    task = db.query(models.OrchestrationTask).filter(models.OrchestrationTask.id == task_id).first()
    if not task:
        logger.warning(f"Task with ID {task_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with ID {task_id} not found")
    return task

def create_log_entry(db: Session, task_id: int, level: str, message: str, details: Optional[dict] = None):
    """Creates and commits a new activity log entry for a task."""
    log_entry = models.ActivityLog(
        task_id=task_id,
        level=level,
        message=message,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.OrchestrationTaskResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new AI Orchestration Task"
)
def create_task(task: models.OrchestrationTaskCreate, db: Session = Depends(get_db)):
    """
    Creates a new AI Orchestration Task with a defined pipeline.
    The task is initially set to PENDING status.
    """
    db_task = models.OrchestrationTask(
        name=task.name,
        description=task.description,
        pipeline_definition=task.pipeline_definition,
        input_data=task.input_data,
        status=models.TaskStatus.PENDING.value
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    create_log_entry(db, db_task.id, "INFO", "Task created successfully.", {"initial_status": db_task.status})
    logger.info(f"Task created: ID {db_task.id}, Name '{db_task.name}'")
    
    return db_task

@router.get(
    "/{task_id}", 
    response_model=models.OrchestrationTaskResponse,
    summary="Retrieve a specific AI Orchestration Task"
)
def read_task(task_id: int, db: Session = Depends(get_db)):
    """
    Retrieves the details of a single AI Orchestration Task, including its logs.
    """
    db_task = get_task_or_404(db, task_id)
    return db_task

@router.get(
    "/", 
    response_model=List[models.OrchestrationTaskResponse],
    summary="List all AI Orchestration Tasks"
)
def list_tasks(
    status_filter: Optional[models.TaskStatus] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all AI Orchestration Tasks, with optional filtering by status and pagination.
    """
    query = db.query(models.OrchestrationTask)
    
    if status_filter:
        query = query.filter(models.OrchestrationTask.status == status_filter.value)
        
    tasks = query.offset(skip).limit(limit).all()
    return tasks

@router.put(
    "/{task_id}", 
    response_model=models.OrchestrationTaskResponse,
    summary="Update an existing AI Orchestration Task"
)
def update_task(task_id: int, task: models.OrchestrationTaskUpdate, db: Session = Depends(get_db)):
    """
    Updates the details of an existing AI Orchestration Task.
    """
    db_task = get_task_or_404(db, task_id)
    
    update_data = task.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        if key == "status" and isinstance(value, models.TaskStatus):
            setattr(db_task, key, value.value)
            create_log_entry(db, task_id, "INFO", f"Task status updated to {value.value}.", {"old_status": db_task.status, "new_status": value.value})
        else:
            setattr(db_task, key, value)
            
    db.commit()
    db.refresh(db_task)
    
    logger.info(f"Task updated: ID {db_task.id}")
    return db_task

@router.delete(
    "/{task_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an AI Orchestration Task"
)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """
    Deletes a specific AI Orchestration Task and all associated activity logs.
    """
    db_task = get_task_or_404(db, task_id)
    
    db.delete(db_task)
    db.commit()
    
    logger.info(f"Task deleted: ID {task_id}")
    return

# --- Business Logic Endpoints ---

@router.post(
    "/{task_id}/start", 
    response_model=models.OrchestrationTaskResponse,
    summary="Start an AI Orchestration Task"
)
def start_task(task_id: int, db: Session = Depends(get_db)):
    """
    Changes the task status to RUNNING, simulating the start of the orchestration process.
    Only tasks in PENDING or PAUSED status can be started/resumed.
    """
    db_task = get_task_or_404(db, task_id)
    
    if db_task.status in [models.TaskStatus.PENDING.value, models.TaskStatus.PAUSED.value]:
        db_task.status = models.TaskStatus.RUNNING.value
        db.commit()
        db.refresh(db_task)
        create_log_entry(db, task_id, "INFO", "Task started/resumed.", {"new_status": db_task.status})
        logger.info(f"Task ID {task_id} status set to RUNNING.")
        return db_task
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is currently in {db_task.status} status and cannot be started."
        )

@router.post(
    "/{task_id}/pause", 
    response_model=models.OrchestrationTaskResponse,
    summary="Pause an AI Orchestration Task"
)
def pause_task(task_id: int, db: Session = Depends(get_db)):
    """
    Changes the task status to PAUSED, simulating a temporary halt in the orchestration process.
    Only tasks in RUNNING status can be paused.
    """
    db_task = get_task_or_404(db, task_id)
    
    if db_task.status == models.TaskStatus.RUNNING.value:
        db_task.status = models.TaskStatus.PAUSED.value
        db.commit()
        db.refresh(db_task)
        create_log_entry(db, task_id, "WARNING", "Task paused.", {"new_status": db_task.status})
        logger.warning(f"Task ID {task_id} status set to PAUSED.")
        return db_task
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is currently in {db_task.status} status and cannot be paused."
        )

@router.post(
    "/{task_id}/complete", 
    response_model=models.OrchestrationTaskResponse,
    summary="Mark an AI Orchestration Task as Completed"
)
def complete_task(task_id: int, output_data: dict, db: Session = Depends(get_db)):
    """
    Marks the task as COMPLETED and stores the final output data.
    """
    db_task = get_task_or_404(db, task_id)
    
    if db_task.status not in [models.TaskStatus.COMPLETED.value, models.TaskStatus.FAILED.value, models.TaskStatus.CANCELLED.value]:
        db_task.status = models.TaskStatus.COMPLETED.value
        db_task.output_data = output_data
        db.commit()
        db.refresh(db_task)
        create_log_entry(db, task_id, "SUCCESS", "Task completed successfully.", {"new_status": db_task.status})
        logger.info(f"Task ID {task_id} status set to COMPLETED.")
        return db_task
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is already in a terminal state: {db_task.status}."
        )

@router.get(
    "/{task_id}/logs", 
    response_model=List[models.ActivityLogResponse],
    summary="Retrieve Activity Logs for a Task"
)
def get_task_logs(task_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves the activity log entries for a specific AI Orchestration Task.
    """
    # Ensure the task exists
    get_task_or_404(db, task_id)
    
    logs = db.query(models.ActivityLog).filter(models.ActivityLog.task_id == task_id).offset(skip).limit(limit).all()
    return logs
