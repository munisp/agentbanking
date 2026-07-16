import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, update as sql_update, delete as sql_delete

from .config import get_db
from .models import (
    ETLPipeline, ETLPipelineActivityLog, ETLPipelineCreate, ETLPipelineUpdate,
    ETLPipelineResponse, ETLPipelineDetailResponse, PipelineStatus, ActivityType
)

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Router Initialization ---
router = APIRouter(
    prefix="/etl-pipelines",
    tags=["ETL Pipelines"],
    responses={404: {"description": "Not found"}},
)

# --- CRUD Helper Functions ---

def get_pipeline_by_id(db: Session, pipeline_id: int) -> ETLPipeline:
    """Fetches an ETLPipeline by its ID, raising 404 if not found or deleted."""
    pipeline = db.get(ETLPipeline, pipeline_id)
    if not pipeline or pipeline.is_deleted:
        logger.warning(f"ETL Pipeline with ID {pipeline_id} not found or is deleted.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ETL Pipeline with ID {pipeline_id} not found."
        )
    return pipeline

def log_activity(db: Session, pipeline_id: int, activity_type: ActivityType, details: Optional[str] = None, user_id: Optional[str] = "system"):
    """Creates an activity log entry for a pipeline."""
    log_entry = ETLPipelineActivityLog(
        pipeline_id=pipeline_id,
        activity_type=activity_type,
        details=details,
        user_id=user_id
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Logged activity for pipeline {pipeline_id}: {activity_type.value}")

# --- Endpoints ---

@router.post(
    "/",
    response_model=ETLPipelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ETL Pipeline"
)
def create_pipeline(pipeline: ETLPipelineCreate, db: Session = Depends(get_db)):
    """
    Creates a new ETL Pipeline configuration in the database.
    The initial status is set to DRAFT.
    """
    # Check for existing pipeline with the same name
    existing_pipeline = db.scalar(
        select(ETLPipeline).where(ETLPipeline.name == pipeline.name)
    )
    if existing_pipeline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ETL Pipeline with name '{pipeline.name}' already exists."
        )

    db_pipeline = ETLPipeline(**pipeline.model_dump())
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    
    log_activity(db, db_pipeline.id, ActivityType.CREATE, "Pipeline created.")
    logger.info(f"Created new ETL Pipeline: {db_pipeline.id}")
    return db_pipeline

@router.get(
    "/",
    response_model=List[ETLPipelineResponse],
    summary="List all ETL Pipelines"
)
def list_pipelines(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination."),
    limit: int = Query(100, le=1000, description="Maximum number of records to return."),
    status_filter: Optional[PipelineStatus] = Query(None, description="Filter by pipeline status."),
    include_deleted: bool = Query(False, description="Include soft-deleted pipelines in the results.")
):
    """
    Retrieves a list of ETL Pipeline configurations, supporting pagination and filtering.
    By default, soft-deleted pipelines are excluded.
    """
    stmt = select(ETLPipeline)
    
    if not include_deleted:
        stmt = stmt.where(ETLPipeline.is_deleted == False)
        
    if status_filter:
        stmt = stmt.where(ETLPipeline.status == status_filter)
        
    pipelines = db.scalars(stmt.offset(skip).limit(limit)).all()
    return pipelines

@router.get(
    "/{pipeline_id}",
    response_model=ETLPipelineDetailResponse,
    summary="Get a specific ETL Pipeline by ID"
)
def read_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single ETL Pipeline configuration and its associated activity logs.
    """
    pipeline = get_pipeline_by_id(db, pipeline_id)
    return pipeline

@router.put(
    "/{pipeline_id}",
    response_model=ETLPipelineResponse,
    summary="Update an existing ETL Pipeline"
)
def update_pipeline(pipeline_id: int, pipeline_update: ETLPipelineUpdate, db: Session = Depends(get_db)):
    """
    Updates the configuration of an existing ETL Pipeline.
    """
    db_pipeline = get_pipeline_by_id(db, pipeline_id)
    
    update_data = pipeline_update.model_dump(exclude_unset=True)
    
    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != db_pipeline.name:
        existing_pipeline = db.scalar(
            select(ETLPipeline).where(ETLPipeline.name == update_data["name"], ETLPipeline.id != pipeline_id)
        )
        if existing_pipeline:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ETL Pipeline with name '{update_data['name']}' already exists."
            )

    for key, value in update_data.items():
        setattr(db_pipeline, key, value)

    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    
    log_activity(db, pipeline_id, ActivityType.UPDATE, "Pipeline configuration updated.")
    logger.info(f"Updated ETL Pipeline: {pipeline_id}")
    return db_pipeline

@router.delete(
    "/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an ETL Pipeline"
)
def delete_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    """
    Soft-deletes an ETL Pipeline by setting the `is_deleted` flag to True.
    The record remains in the database.
    """
    db_pipeline = get_pipeline_by_id(db, pipeline_id)
    
    if db_pipeline.is_deleted:
        # Already deleted, no action needed, but return 204
        return
        
    db_pipeline.is_deleted = True
    db.add(db_pipeline)
    db.commit()
    
    log_activity(db, pipeline_id, ActivityType.DELETE, "Pipeline soft-deleted.")
    logger.info(f"Soft-deleted ETL Pipeline: {pipeline_id}")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{pipeline_id}/execute",
    response_model=ETLPipelineResponse,
    summary="Execute the ETL Pipeline"
)
def execute_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    """
    Triggers the execution of the specified ETL Pipeline.
    Triggers ETL pipeline execution via the configured orchestrator.
    """
    db_pipeline = get_pipeline_by_id(db, pipeline_id)
    
    if db_pipeline.status not in [PipelineStatus.ACTIVE, PipelineStatus.INACTIVE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute pipeline in {db_pipeline.status.value} status. Must be ACTIVE or INACTIVE."
        )
        
    # Trigger execution via orchestrator
    db_pipeline.status = PipelineStatus.RUNNING
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    
    log_activity(db, pipeline_id, ActivityType.EXECUTE, "Execution triggered.")
    logger.info(f"Execution triggered for ETL Pipeline: {pipeline_id}")
    
    # In a real application, this would trigger an asynchronous job (e.g., Celery, Kafka message)
    # and the status would be updated by the worker process.
    
    return db_pipeline

@router.patch(
    "/{pipeline_id}/status",
    response_model=ETLPipelineResponse,
    summary="Change the status of the ETL Pipeline"
)
def change_pipeline_status(
    pipeline_id: int, 
    new_status: PipelineStatus = Query(..., description="The new status to set for the pipeline."),
    db: Session = Depends(get_db)
):
    """
    Allows changing the operational status of the ETL Pipeline (e.g., to ACTIVE, INACTIVE).
    """
    db_pipeline = get_pipeline_by_id(db, pipeline_id)
    
    if db_pipeline.status == new_status:
        return db_pipeline
        
    if new_status == PipelineStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot manually set status to RUNNING. Use the /execute endpoint."
        )

    old_status = db_pipeline.status
    db_pipeline.status = new_status
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    
    log_activity(
        db, 
        pipeline_id, 
        ActivityType.UPDATE, 
        f"Status changed from {old_status.value} to {new_status.value}."
    )
    logger.info(f"Status of ETL Pipeline {pipeline_id} changed to {new_status.value}")
    
    return db_pipeline
