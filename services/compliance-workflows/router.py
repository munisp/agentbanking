import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from . import models
from .config import get_db

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router Initialization ---
router = APIRouter(
    prefix="/workflows",
    tags=["compliance-workflows"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_workflow_or_404(db: Session, workflow_id: int) -> models.ComplianceWorkflow:
    """
    Helper function to fetch a workflow by ID or raise a 404 exception.
    """
    workflow = db.query(models.ComplianceWorkflow).filter(models.ComplianceWorkflow.id == workflow_id).first()
    if not workflow:
        logger.warning(f"Workflow with ID {workflow_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow with ID {workflow_id} not found")
    return workflow

def create_log_entry(db: Session, workflow_id: int, log_data: models.ActivityLogCreate):
    """
    Creates and commits a new activity log entry for a workflow.
    """
    db_log = models.ActivityLog(**log_data.model_dump(), workflow_id=workflow_id)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

# --- CRUD Endpoints for ComplianceWorkflow ---

@router.post(
    "/",
    response_model=models.ComplianceWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Compliance Workflow",
    description="Creates a new compliance workflow instance for a specified entity."
)
def create_workflow(workflow: models.ComplianceWorkflowCreate, db: Session = Depends(get_db)):
    """
    Create a new Compliance Workflow.
    """
    try:
        db_workflow = models.ComplianceWorkflow(**workflow.model_dump())
        db.add(db_workflow)
        db.commit()
        db.refresh(db_workflow)
        
        # Log creation
        create_log_entry(db, db_workflow.id, models.ActivityLogCreate(
            log_level=models.LogLevel.INFO,
            message="Workflow created successfully.",
            details=f"Initial status: {db_workflow.status}"
        ))
        
        logger.info(f"Created new workflow with ID: {db_workflow.id}")
        return db_workflow
    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@router.get(
    "/",
    response_model=List[models.ComplianceWorkflowResponse],
    summary="List all Compliance Workflows",
    description="Retrieves a list of all compliance workflows with optional filtering and pagination."
)
def list_workflows(
    status_filter: Optional[models.WorkflowStatus] = Query(None, description="Filter by workflow status"),
    entity_type: Optional[models.EntityType] = Query(None, description="Filter by entity type"),
    skip: int = Query(0, ge=0, description="Number of items to skip (offset)"),
    limit: int = Query(100, le=100, description="Maximum number of items to return"),
    db: Session = Depends(get_db)
):
    """
    List all Compliance Workflows with filtering and pagination.
    """
    query = db.query(models.ComplianceWorkflow)
    
    if status_filter:
        query = query.filter(models.ComplianceWorkflow.status == status_filter.value)
    
    if entity_type:
        query = query.filter(models.ComplianceWorkflow.entity_type == entity_type.value)
        
    workflows = query.offset(skip).limit(limit).all()
    return workflows

@router.get(
    "/{workflow_id}",
    response_model=models.ComplianceWorkflowResponse,
    summary="Get a Compliance Workflow by ID",
    description="Retrieves a single compliance workflow instance by its unique ID."
)
def read_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """
    Get a Compliance Workflow by ID.
    """
    return get_workflow_or_404(db, workflow_id)

@router.put(
    "/{workflow_id}",
    response_model=models.ComplianceWorkflowResponse,
    summary="Update a Compliance Workflow",
    description="Updates the details of an existing compliance workflow."
)
def update_workflow(workflow_id: int, workflow_update: models.ComplianceWorkflowUpdate, db: Session = Depends(get_db)):
    """
    Update a Compliance Workflow.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    update_data = workflow_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
        
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    
    # Log update
    create_log_entry(db, db_workflow.id, models.ActivityLogCreate(
        log_level=models.LogLevel.INFO,
        message="Workflow updated.",
        details=f"Fields updated: {', '.join(update_data.keys())}"
    ))
    
    logger.info(f"Updated workflow with ID: {workflow_id}")
    return db_workflow

@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Compliance Workflow",
    description="Deletes a compliance workflow instance and all associated activity logs."
)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """
    Delete a Compliance Workflow.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    db.delete(db_workflow)
    db.commit()
    
    logger.info(f"Deleted workflow with ID: {workflow_id}")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{workflow_id}/advance",
    response_model=models.ComplianceWorkflowResponse,
    summary="Advance Workflow Status",
    description="Attempts to advance the workflow to the next logical status. This is a business-specific action."
)
def advance_workflow(workflow_id: int, new_status: models.WorkflowStatus, db: Session = Depends(get_db)):
    """
    Advance the status of a Compliance Workflow.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    old_status = db_workflow.status
    
    if old_status == new_status.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow is already in status: {new_status.value}"
        )
        
    # Simple state transition logic (can be expanded with complex business rules)
    db_workflow.status = new_status.value
    
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    
    # Log status change
    create_log_entry(db, db_workflow.id, models.ActivityLogCreate(
        log_level=models.LogLevel.INFO,
        message="Workflow status advanced.",
        details=f"Status changed from {old_status} to {new_status.value}"
    ))
    
    logger.info(f"Workflow {workflow_id} status advanced to {new_status.value}")
    return db_workflow

@router.get(
    "/{workflow_id}/logs",
    response_model=List[models.ActivityLogResponse],
    summary="Get Activity Logs for a Workflow",
    description="Retrieves all activity logs for a specific compliance workflow, ordered by timestamp."
)
def get_workflow_logs(
    workflow_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db)
):
    """
    Get Activity Logs for a Workflow.
    """
    # Ensure the workflow exists
    get_workflow_or_404(db, workflow_id)
    
    logs = db.query(models.ActivityLog).filter(models.ActivityLog.workflow_id == workflow_id)\
        .order_by(desc(models.ActivityLog.timestamp))\
        .offset(skip).limit(limit).all()
        
    return logs

@router.post(
    "/{workflow_id}/logs",
    response_model=models.ActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an Activity Log Entry",
    description="Adds a new activity log entry to a specific compliance workflow."
)
def add_workflow_log(workflow_id: int, log_data: models.ActivityLogCreate, db: Session = Depends(get_db)):
    """
    Add an Activity Log Entry to a Workflow.
    """
    # Ensure the workflow exists
    get_workflow_or_404(db, workflow_id)
    
    db_log = create_log_entry(db, workflow_id, log_data)
    
    logger.info(f"Added log to workflow {workflow_id}: {log_data.message}")
    return db_log
