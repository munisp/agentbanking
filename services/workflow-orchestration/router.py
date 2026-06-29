import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def get_workflow_or_404(db: Session, workflow_id: uuid.UUID) -> models.Workflow:
    """
    Fetches a workflow by ID or raises a 404 HTTP exception.
    """
    workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    if not workflow:
        logger.warning(f"Workflow with ID {workflow_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    return workflow

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workflow",
    description="Creates a new workflow definition in the system. The initial status is DRAFT."
)
def create_workflow(
    workflow_in: models.WorkflowCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new workflow in the database.

    Args:
        workflow_in: The Pydantic model for creating a workflow.
        db: The database session dependency.

    Returns:
        The created Workflow object.

    Raises:
        HTTPException: 409 Conflict if a workflow with the same name already exists.
    """
    logger.info(f"Attempting to create new workflow: {workflow_in.name}")
    db_workflow = models.Workflow(**workflow_in.model_dump())
    
    try:
        db.add(db_workflow)
        db.commit()
        db.refresh(db_workflow)
        logger.info(f"Successfully created workflow with ID: {db_workflow.id}")
        return db_workflow
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error: Workflow name '{workflow_in.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow with name '{workflow_in.name}' already exists."
        )

@router.get(
    "/",
    response_model=List[models.WorkflowResponse],
    summary="List all workflows",
    description="Retrieves a list of all workflow definitions."
)
def list_workflows(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[models.WorkflowStatus] = None
):
    """
    Retrieves a list of workflows with optional filtering and pagination.

    Args:
        db: The database session dependency.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return.
        status_filter: Optional filter by workflow status.

    Returns:
        A list of Workflow objects.
    """
    query = db.query(models.Workflow)
    if status_filter:
        query = query.filter(models.Workflow.status == status_filter)
        
    workflows = query.offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(workflows)} workflows.")
    return workflows

@router.get(
    "/{workflow_id}",
    response_model=models.WorkflowWithLogsResponse,
    summary="Get a workflow by ID with activity logs",
    description="Retrieves a specific workflow definition and its associated activity logs."
)
def read_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves a single workflow by its ID.

    Args:
        workflow_id: The unique identifier of the workflow.
        db: The database session dependency.

    Returns:
        The Workflow object including its activity logs.

    Raises:
        HTTPException: 404 Not Found if the workflow does not exist.
    """
    # Eagerly load activity_logs for a single query
    workflow = db.query(models.Workflow).filter(models.Workflow.id == workflow_id).first()
    
    if not workflow:
        logger.warning(f"Workflow with ID {workflow_id} not found for read operation.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID {workflow_id} not found"
        )
    
    logger.info(f"Retrieved workflow with ID: {workflow_id}")
    return workflow

@router.put(
    "/{workflow_id}",
    response_model=models.WorkflowResponse,
    summary="Update an existing workflow",
    description="Updates the details of an existing workflow. Only non-null fields in the request body will be updated."
)
def update_workflow(
    workflow_id: uuid.UUID,
    workflow_in: models.WorkflowUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates an existing workflow in the database.

    Args:
        workflow_id: The unique identifier of the workflow to update.
        workflow_in: The Pydantic model for updating a workflow.
        db: The database session dependency.

    Returns:
        The updated Workflow object.

    Raises:
        HTTPException: 404 Not Found if the workflow does not exist.
        HTTPException: 409 Conflict if the update causes a name collision.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    update_data = workflow_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
        
    try:
        db.add(db_workflow)
        db.commit()
        db.refresh(db_workflow)
        logger.info(f"Successfully updated workflow with ID: {workflow_id}")
        return db_workflow
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error during update for workflow ID {workflow_id}.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update failed: A workflow with the provided name might already exist."
        )

@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workflow",
    description="Deletes a workflow definition and all its associated activity logs."
)
def delete_workflow(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Deletes a workflow from the database.

    Args:
        workflow_id: The unique identifier of the workflow to delete.
        db: The database session dependency.

    Raises:
        HTTPException: 404 Not Found if the workflow does not exist.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    db.delete(db_workflow)
    db.commit()
    logger.info(f"Successfully deleted workflow with ID: {workflow_id}")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{workflow_id}/run",
    response_model=models.WorkflowActivityLogResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a workflow run",
    description="Triggers the execution of an active workflow and logs the start event."
)
def trigger_workflow_run(
    workflow_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Triggers the execution of a workflow.

    Args:
        workflow_id: The unique identifier of the workflow to run.
        db: The database session dependency.

    Returns:
        A log entry indicating the workflow has been triggered.

    Raises:
        HTTPException: 404 Not Found if the workflow does not exist.
        HTTPException: 400 Bad Request if the workflow is not in an ACTIVE status.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    if db_workflow.status != models.WorkflowStatus.ACTIVE:
        logger.warning(f"Attempted to run non-active workflow ID {workflow_id} (Status: {db_workflow.status}).")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow must be in ACTIVE status to run. Current status: {db_workflow.status}"
        )
        
    # Trigger workflow run via orchestrator (queue message or service call)
    run_id = str(uuid.uuid4())
    
    # Create an activity log entry for the run
    log_entry = models.WorkflowActivityLog(
        workflow_id=workflow_id,
        event_type="WORKFLOW_TRIGGERED",
        details={"run_id": run_id, "trigger_type": "API_CALL", "message": "Workflow execution initiated."}
    )
    
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    
    logger.info(f"Workflow ID {workflow_id} triggered. Run ID: {run_id}")
    
    return log_entry

@router.post(
    "/{workflow_id}/status/{new_status}",
    response_model=models.WorkflowResponse,
    summary="Change workflow status",
    description="Manually changes the status of a workflow (e.g., from DRAFT to ACTIVE)."
)
def change_workflow_status(
    workflow_id: uuid.UUID,
    new_status: models.WorkflowStatus,
    db: Session = Depends(get_db)
):
    """
    Changes the status of a workflow.

    Args:
        workflow_id: The unique identifier of the workflow.
        new_status: The new status to set.
        db: The database session dependency.

    Returns:
        The updated Workflow object.

    Raises:
        HTTPException: 404 Not Found if the workflow does not exist.
    """
    db_workflow = get_workflow_or_404(db, workflow_id)
    
    if db_workflow.status == new_status:
        logger.info(f"Workflow ID {workflow_id} status is already {new_status}. No change made.")
        return db_workflow
        
    db_workflow.status = new_status
    
    # Log the status change
    log_entry = models.WorkflowActivityLog(
        workflow_id=workflow_id,
        event_type="STATUS_CHANGE",
        details={"old_status": str(db_workflow.status), "new_status": str(new_status)}
    )
    
    db.add(log_entry)
    db.commit()
    db.refresh(db_workflow)
    
    logger.info(f"Workflow ID {workflow_id} status changed to {new_status}.")
    
    return db_workflow
