import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from . import models, config
from .models import GNNJob, JobStatus, ActivityLog
from .models import GNNJobCreate, GNNJobUpdate, GNNJobResponse, GNNJobListResponse

# --- Logger Setup ---
logger = logging.getLogger(config.get_settings().SERVICE_NAME)
logger.setLevel(logging.INFO)

# --- Router Initialization ---
router = APIRouter(
    prefix="/jobs",
    tags=["GNN Jobs"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the database session
get_db = config.get_db

# --- Helper Functions ---

def get_job_or_404(db: Session, job_id: int) -> GNNJob:
    """Fetches a GNNJob by ID or raises a 404 error."""
    job = db.query(GNNJob).filter(GNNJob.id == job_id).first()
    if not job:
        logger.warning(f"GNNJob with ID {job_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GNN Job with ID {job_id} not found"
        )
    return job

def create_activity_log(db: Session, job_id: int, level: str, message: str):
    """Creates and commits a new activity log entry."""
    log_entry = ActivityLog(
        job_id=job_id,
        level=level,
        message=message
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Job {job_id} logged: [{level}] {message}")


# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=GNNJobResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new GNN Job"
)
def create_gnn_job(job: GNNJobCreate, db: Session = Depends(get_db)):
    """
    Registers a new GNN job (e.g., training or inference). 
    The job is initially set to PENDING status.
    """
    try:
        db_job = GNNJob(**job.model_dump())
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        
        create_activity_log(db, db_job.id, "INFO", "Job created and set to PENDING.")
        
        logger.info(f"Created new GNN Job: ID={db_job.id}, Name={db_job.job_name}")
        return db_job
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating GNN Job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the job: {e}"
        )

@router.get(
    "/{job_id}", 
    response_model=GNNJobResponse,
    summary="Retrieve a GNN Job by ID"
)
def read_gnn_job(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieves the details of a specific GNN job, including its full activity log.
    """
    db_job = get_job_or_404(db, job_id)
    return db_job

@router.get(
    "/", 
    response_model=List[GNNJobListResponse],
    summary="List all GNN Jobs"
)
def list_gnn_jobs(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    status_filter: Optional[JobStatus] = Query(None, alias="status", description="Filter by job status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of GNN jobs with optional filtering and pagination.
    The list response excludes the full activity log for brevity.
    """
    query = db.query(GNNJob)
    
    if tenant_id:
        query = query.filter(GNNJob.tenant_id == tenant_id)
    
    if status_filter:
        query = query.filter(GNNJob.status == status_filter)
        
    jobs = query.order_by(desc(GNNJob.created_at)).offset(skip).limit(limit).all()
    
    return jobs

@router.put(
    "/{job_id}", 
    response_model=GNNJobResponse,
    summary="Update an existing GNN Job"
)
def update_gnn_job(job_id: int, job_update: GNNJobUpdate, db: Session = Depends(get_db)):
    """
    Updates the details of an existing GNN job. 
    Note: Status changes should typically be handled by the internal engine, 
    but this endpoint allows for manual updates.
    """
    db_job = get_job_or_404(db, job_id)
    
    update_data = job_update.model_dump(exclude_unset=True)
    
    # Handle status change and set timestamps
    if "status" in update_data and update_data["status"] != db_job.status:
        new_status = update_data["status"]
        log_message = f"Status changed from {db_job.status.value} to {new_status.value}."
        
        if new_status == JobStatus.RUNNING and db_job.started_at is None:
            db_job.started_at = datetime.utcnow()
            log_message += " Job started."
        elif new_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and db_job.completed_at is None:
            db_job.completed_at = datetime.utcnow()
            log_message += " Job finished."
            
        create_activity_log(db, job_id, "STATUS_CHANGE", log_message)

    for key, value in update_data.items():
        setattr(db_job, key, value)

    db.commit()
    db.refresh(db_job)
    
    logger.info(f"Updated GNN Job: ID={db_job.id}")
    return db_job

@router.delete(
    "/{job_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a GNN Job"
)
def delete_gnn_job(job_id: int, db: Session = Depends(get_db)):
    """
    Deletes a GNN job and all associated activity logs.
    """
    db_job = get_job_or_404(db, job_id)
    
    db.delete(db_job)
    db.commit()
    
    logger.info(f"Deleted GNN Job: ID={job_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.post(
    "/{job_id}/trigger",
    response_model=GNNJobResponse,
    summary="Trigger the execution of a PENDING GNN Job"
)
def trigger_gnn_job(job_id: int, db: Session = Depends(get_db)):
    """
    Computes triggering the GNN engine to start processing a PENDING job.
    The job status is updated to RUNNING and the started_at timestamp is set.
    """
    db_job = get_job_or_404(db, job_id)
    
    if db_job.status != JobStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is already {db_job.status.value}. Only PENDING jobs can be triggered."
        )
        
    # Start the computation job
    db_job.status = JobStatus.RUNNING
    db_job.started_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_job)
    
    create_activity_log(db, job_id, "ENGINE", "Job execution triggered and set to RUNNING.")
    
    logger.info(f"Triggered GNN Job: ID={job_id}")
    return db_job

@router.post(
    "/{job_id}/log",
    response_model=GNNJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity log entry to a GNN Job"
)
def add_job_log(job_id: int, log_entry: models.ActivityLogBase, db: Session = Depends(get_db)):
    """
    Allows the GNN engine or external services to add a custom log entry 
    to the job's activity log.
    """
    db_job = get_job_or_404(db, job_id)
    
    create_activity_log(db, job_id, log_entry.level, log_entry.message)
    
    # Refresh the job to include the new log entry in the response
    db.refresh(db_job)
    
    return db_job
