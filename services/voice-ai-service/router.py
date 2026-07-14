import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

# Assuming config.py and models.py are in the same directory
from config import get_db, get_settings
from models import (
    Base,
    VoiceJob,
    VoiceJobCreate,
    VoiceJobUpdate,
    VoiceJobResponse,
    ActivityLog,
    ActivityLogResponse,
)

# Initialize logging
settings = get_settings()
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/jobs",
    tags=["voice-jobs"],
    responses={404: {"description": "Not found"}},
)

# Helper function to create tables (typically done in main.py, but included for completeness)
def create_db_tables(db_engine):
    """Creates all defined database tables."""
    Base.metadata.create_all(bind=db_engine)


# --- CRUD Endpoints for VoiceJob ---

@router.post(
    "/",
    response_model=VoiceJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Voice AI Job",
    description="Submits a new voice processing job (e.g., transcription, synthesis) to the system.",
)
def create_voice_job(
    job: VoiceJobCreate, db: Session = Depends(get_db)
):
    """
    Creates a new VoiceJob entry in the database.
    """
    logger.info(f"Creating new job for user {job.user_id} of type {job.job_type}")
    
    # Check for job duration limit (business logic example)
    if job.job_type == "transcription" and settings.MAX_JOB_DURATION_SECONDS < 3600:
        # This is a placeholder for a real-world check, assuming we know the duration
        # before submission, which is not possible here. A real check would happen
        # in a processing service. We'll use a simple check on the input URL for now.
        pass

    db_job = VoiceJob(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # Log the creation activity
    log_entry = ActivityLog(
        job_id=db_job.id,
        activity_type="job_created",
        details=f"Job {db_job.id} created with type {db_job.job_type}",
    )
    db.add(log_entry)
    db.commit()
    
    logger.info(f"Job {db_job.id} created successfully.")
    return db_job


@router.get(
    "/{job_id}",
    response_model=VoiceJobResponse,
    summary="Get a Voice AI Job by ID",
    description="Retrieves the details of a specific voice processing job.",
)
def read_voice_job(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a VoiceJob by its ID. Raises 404 if not found.
    """
    db_job = db.query(VoiceJob).filter(VoiceJob.id == job_id).first()
    if db_job is None:
        logger.warning(f"Job {job_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Voice Job not found"
        )
    return db_job


@router.get(
    "/",
    response_model=List[VoiceJobResponse],
    summary="List Voice AI Jobs",
    description="Retrieves a list of voice processing jobs, with optional filtering by user ID and status.",
)
def list_voice_jobs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by job status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
):
    """
    Lists VoiceJob entries with pagination and optional filtering.
    """
    query = db.query(VoiceJob)
    if user_id is not None:
        query = query.filter(VoiceJob.user_id == user_id)
    if status_filter is not None:
        query = query.filter(VoiceJob.status == status_filter)

    jobs = query.offset(skip).limit(limit).all()
    return jobs


@router.put(
    "/{job_id}",
    response_model=VoiceJobResponse,
    summary="Update a Voice AI Job",
    description="Updates the status or details of an existing voice processing job.",
)
def update_voice_job(
    job_id: int, job_update: VoiceJobUpdate, db: Session = Depends(get_db)
):
    """
    Updates an existing VoiceJob by ID.
    """
    db_job = read_voice_job(job_id=job_id, db=db)  # Reuses read logic for existence check

    update_data = job_update.model_dump(exclude_unset=True)
    
    # Check if status is being updated
    if "status" in update_data and update_data["status"] != db_job.status:
        old_status = db_job.status
        new_status = update_data["status"]
        
        # Log the status change
        log_entry = ActivityLog(
            job_id=job_id,
            activity_type="status_change",
            details=f"Status changed from '{old_status}' to '{new_status}'",
        )
        db.add(log_entry)
        logger.info(f"Job {job_id}: Status changed from {old_status} to {new_status}")

    for key, value in update_data.items():
        setattr(db_job, key, value)

    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Voice AI Job",
    description="Deletes a voice processing job and all associated activity logs.",
)
def delete_voice_job(job_id: int, db: Session = Depends(get_db)):
    """
    Deletes a VoiceJob by its ID.
    """
    db_job = read_voice_job(job_id=job_id, db=db)  # Reuses read logic for existence check

    db.delete(db_job)
    db.commit()
    
    logger.info(f"Job {job_id} and associated logs deleted.")
    return {"ok": True}


# --- Business-Specific Endpoints ---

@router.post(
    "/{job_id}/start_processing",
    response_model=VoiceJobResponse,
    summary="Simulate starting job processing",
    description="Marks a job as 'processing' and processs the start of the AI task.",
)
def start_processing(job_id: int, db: Session = Depends(get_db)):
    """
    Processes an external worker picking up the job and starting processing.
    """
    db_job = read_voice_job(job_id=job_id, db=db)

    if db_job.status not in ["pending", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is already in status: {db_job.status}",
        )

    # Update status
    db_job.status = "processing"
    db.add(db_job)
    
    # Log the activity
    log_entry = ActivityLog(
        job_id=job_id,
        activity_type="processing_started",
        details=f"Processing started using model: {db_job.model_used}",
    )
    db.add(log_entry)
    
    db.commit()
    db.refresh(db_job)
    logger.info(f"Job {job_id} marked as 'processing'.")
    return db_job


@router.get(
    "/{job_id}/logs",
    response_model=List[ActivityLogResponse],
    summary="Get Activity Logs for a Job",
    description="Retrieves the chronological activity log for a specific voice processing job.",
)
def get_job_logs(job_id: int, db: Session = Depends(get_db)):
    """
    Retrieves all activity logs associated with a given VoiceJob ID.
    """
    # Ensure the job exists
    read_voice_job(job_id=job_id, db=db)
    
    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.job_id == job_id)
        .order_by(ActivityLog.timestamp.asc())
        .all()
    )
    return logs
