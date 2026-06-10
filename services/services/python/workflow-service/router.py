import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db, get_settings, logger
from .models import WorkflowStatus

# Initialize router
router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def get_workflow_or_404(db: Session, workflow_id: int) -> models.Workflow:
    """Fetches a workflow by ID or raises a 404 HTTP exception."""
    db_workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if db_workflow is None:
        logger.warning(f"Workflow with ID {workflow_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    return db_workflow

def create_activity_log(db: Session, workflow_id: int, activity_type: str, user_id: Optional[int] = None, details: Optional[dict] = None):
    """Creates and commits a new activity log entry."""
    log_entry = models.ActivityLogCreate(
        workflow_id=workflow_id,
        activity_type=activity_type,
        user_id=user_id,
        details=details or {}
    )
    db_log = models.ActivityLog(**log_entry.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Activity logged for workflow {workflow_id}: {activity_type}")


# --- Workflow CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.WorkflowResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Workflow"
)
def create_workflow(
    workflow: models.WorkflowCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new workflow definition in the system.
    
    The `definition` field must contain the structure of the workflow, typically a JSON object.
    """
    try:
        db_workflow = models.Workflow(**workflow.model_dump())
        db.add(db_workflow)
        db.commit()
        db.refresh(db_workflow)
        
        # Log creation activity
        create_activity_log(db, db_workflow.id, "created", user_id=workflow.owner_id)
        
        logger.info(f"Workflow created: ID {db_workflow.id}, Name '{db_workflow.name}'")
        return db_workflow
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error when creating workflow: Name '{workflow.name}' likely already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow with name '{workflow.name}' already exists."
        )

@router.get(
    "/{workflow_id}", 
    response_model=models.WorkflowWithLogsResponse,
    summary="Get a Workflow by ID with its Activity Logs"
)
def read_workflow(
    workflow_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single workflow by its ID, including all associated activity logs.
    """
    # Use joinedload to fetch logs in the same query for efficiency
    db_workflow = db.query(models.Workflow).options(joinedload(models.Workflow.activity_logs)).filter(models.Workflow.id == workflow_id).first()
    
    if db_workflow is None:
        logger.warning(f"Attempted to read non-existent workflow ID {workflow_id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    return db_workflow

@router.get(
    "/", 
    response_model=List[models.WorkflowResponse],
    summary="List all Workflows"
)
def list_workflows(
    owner_id: Optional[int] = Query(None, description="Filter by the ID of the workflow owner."),
    status_filter: Optional[WorkflowStatus] = Query(None, alias="status", description="Filter by workflow status."),
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of workflows, with optional filtering by owner and status, and pagination.
    """
    query = db.query(models.Workflow)
    
    if owner_id is not None:
        query = query.filter(models.Workflow.owner_id == owner_id)
        
    if status_filter is not None:
        query = query.filter(models.Workflow.status == status_filter.value)
        
    workflows = query.offset(skip).limit(limit).all()
    
    logger.info(f"Listed {len(workflows)} workflows (skip={skip}, limit={limit}, owner={owner_id}, status={status_filter}).")
    return workflows

@router.put(
    "/{workflow_id}", 
    response_model=models.WorkflowResponse,
    summary="Update an existing Workflow"
)
def update_workflow(
    workflow_id: int, 
    workflow_update: models.WorkflowUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing workflow's details. Only provided fields will be updated.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    update_data = workflow_update.model_dump(exclude_unset=True)
    
    # Check for status change to log it specifically
    old_status = db_workflow.status
    new_status = update_data.get("status")
    
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
        
    try:
        db.commit()
        db.refresh(db_workflow)
        
        # Log status change if it occurred
        if new_status and new_status != old_status:
            create_activity_log(
                db, 
                workflow_id, 
                "status_change", 
                details={"old_status": old_status, "new_status": new_status}
            )
        else:
            create_activity_log(db, workflow_id, "updated")
            
        logger.info(f"Workflow updated: ID {workflow_id}")
        return db_workflow
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error when updating workflow ID {workflow_id}.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update failed due to data integrity violation (e.g., duplicate name)."
        )

@router.delete(
    "/{workflow_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Workflow"
)
def delete_workflow(
    workflow_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a workflow by ID. Associated activity logs are deleted via CASCADE.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    db.delete(db_workflow)
    db.commit()
    
    logger.info(f"Workflow deleted: ID {workflow_id}")
    # No need to log activity as the workflow and its logs are gone

# --- Business-Specific Endpoints ---

@router.post(
    "/{workflow_id}/activate",
    response_model=models.WorkflowResponse,
    summary="Activate a Workflow"
)
def activate_workflow(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Sets the workflow status to 'active'. This typically makes the workflow available for execution.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    if db_workflow.status == WorkflowStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow ID {workflow_id} is already active."
        )
        
    old_status = db_workflow.status
    db_workflow.status = WorkflowStatus.ACTIVE.value
    
    db.commit()
    db.refresh(db_workflow)
    
    create_activity_log(
        db, 
        workflow_id, 
        "status_change", 
        details={"old_status": old_status, "new_status": WorkflowStatus.ACTIVE.value}
    )
    
    logger.info(f"Workflow activated: ID {workflow_id}")
    return db_workflow

@router.post(
    "/{workflow_id}/pause",
    response_model=models.WorkflowResponse,
    summary="Pause a Workflow"
)
def pause_workflow(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Sets the workflow status to 'paused'. This typically stops the workflow from being executed.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    if db_workflow.status == WorkflowStatus.PAUSED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow ID {workflow_id} is already paused."
        )
        
    old_status = db_workflow.status
    db_workflow.status = WorkflowStatus.PAUSED.value
    
    db.commit()
    db.refresh(db_workflow)
    
    create_activity_log(
        db, 
        workflow_id, 
        "status_change", 
        details={"old_status": old_status, "new_status": WorkflowStatus.PAUSED.value}
    )
    
    logger.info(f"Workflow paused: ID {workflow_id}")
    return db_workflow

# --- Activity Log Endpoints (Read-only) ---

@router.get(
    "/{workflow_id}/logs",
    response_model=List[models.ActivityLogResponse],
    summary="Get Activity Logs for a Workflow"
)
def get_workflow_logs(
    workflow_id: int,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves the activity log history for a specific workflow.
    """
    # Ensure the workflow exists
    get_workflow_or_404(db, workflow_id)
    
    logs = db.query(models.ActivityLog).filter(models.ActivityLog.workflow_id == workflow_id).order_by(models.ActivityLog.created_at.desc()).offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(logs)} activity logs for workflow ID {workflow_id}.")
    return logs
