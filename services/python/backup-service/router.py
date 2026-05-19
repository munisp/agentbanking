import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Routers ---
router = APIRouter(
    prefix="/backups",
    tags=["Backup Jobs"],
    responses={404: {"description": "Not found"}},
)

activity_router = APIRouter(
    prefix="/activities",
    tags=["Backup Activities"],
    responses={404: {"description": "Not found"}},
)

# --- Backup Job CRUD Endpoints ---

@router.post(
    "/jobs", 
    response_model=models.BackupJobResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new backup job"
)
def create_backup_job(job: models.BackupJobCreate, db: Session = Depends(get_db)):
    """
    Creates a new backup job with the specified configuration.
    """
    db_job = models.BackupJob(**job.model_dump())
    try:
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        logger.info(f"Created backup job: {db_job.id}")
        return db_job
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating job: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integrity error: A job with this configuration might already exist or data is invalid."
        )

@router.get(
    "/jobs", 
    response_model=List[models.BackupJobResponse],
    summary="List all backup jobs"
)
def list_backup_jobs(
    service_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all backup jobs, with optional filtering by service name and active status.
    """
    query = db.query(models.BackupJob)
    if service_name:
        query = query.filter(models.BackupJob.service_name == service_name)
    if is_active is not None:
        query = query.filter(models.BackupJob.is_active == is_active)
        
    jobs = query.offset(skip).limit(limit).all()
    return jobs

@router.get(
    "/jobs/{job_id}", 
    response_model=models.BackupJobWithActivitiesResponse,
    summary="Get a specific backup job by ID"
)
def get_backup_job(job_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single backup job by its unique ID, including its activity logs.
    """
    db_job = db.query(models.BackupJob).filter(models.BackupJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Job not found")
    return db_job

@router.put(
    "/jobs/{job_id}", 
    response_model=models.BackupJobResponse,
    summary="Update an existing backup job"
)
def update_backup_job(job_id: UUID, job: models.BackupJobUpdate, db: Session = Depends(get_db)):
    """
    Updates the details of an existing backup job.
    """
    db_job = db.query(models.BackupJob).filter(models.BackupJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Job not found")

    update_data = job.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_job, key, value)

    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info(f"Updated backup job: {job_id}")
    return db_job

@router.delete(
    "/jobs/{job_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a backup job"
)
def delete_backup_job(job_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a backup job and all its associated activity logs.
    """
    db_job = db.query(models.BackupJob).filter(models.BackupJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Job not found")

    db.delete(db_job)
    db.commit()
    logger.info(f"Deleted backup job: {job_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.post(
    "/jobs/{job_id}/run",
    response_model=models.BackupActivityLogResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger a backup job run"
)
def run_backup_job(job_id: UUID, db: Session = Depends(get_db)):
    """
    Executes the manual triggering of a backup job. 
    In a real system, this would queue a task for a worker process.
    Here, it creates a 'RUNNING' activity log entry.
    """
    db_job = db.query(models.BackupJob).filter(models.BackupJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Job not found")

    # Create a new activity log entry for the manual run
    activity_data = models.BackupActivityLogCreate(
        job_id=job_id,
        status="RUNNING",
        log_message=f"Manual run triggered for job {job_id}."
    )
    db_activity = models.BackupActivityLog(**activity_data.model_dump())
    
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    
    logger.info(f"Manually triggered run for job {job_id}. Activity ID: {db_activity.id}")
    
    # NOTE: In a real-world scenario, a background task would be initiated here
    # to perform the actual backup and update the activity log status later.
    
    return db_activity

@router.patch(
    "/jobs/{job_id}/toggle_status",
    response_model=models.BackupJobResponse,
    summary="Toggle the active status of a backup job"
)
def toggle_job_status(job_id: UUID, db: Session = Depends(get_db)):
    """
    Toggles the `is_active` status of a backup job between True and False.
    """
    db_job = db.query(models.BackupJob).filter(models.BackupJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Job not found")

    db_job.is_active = not db_job.is_active
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info(f"Toggled active status for job {job_id} to {db_job.is_active}")
    return db_job

# --- Backup Activity Log Endpoints (Sub-router) ---

@activity_router.post(
    "", 
    response_model=models.BackupActivityLogResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new backup activity log entry"
)
def create_activity_log(activity: models.BackupActivityLogCreate, db: Session = Depends(get_db)):
    """
    Creates a new activity log entry, typically used by the background worker 
    to signal the start of a backup process.
    """
    # Check if the job_id exists
    db_job = db.query(models.BackupJob).filter(models.BackupJob.id == activity.job_id).first()
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated Backup Job not found")

    db_activity = models.BackupActivityLog(**activity.model_dump())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    logger.info(f"Created activity log: {db_activity.id} for job {db_activity.job_id}")
    return db_activity

@activity_router.get(
    "", 
    response_model=List[models.BackupActivityLogResponse],
    summary="List all backup activity logs"
)
def list_activity_logs(
    job_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all backup activity logs, with optional filtering by job ID and status.
    """
    query = db.query(models.BackupActivityLog)
    if job_id:
        query = query.filter(models.BackupActivityLog.job_id == job_id)
    if status_filter:
        query = query.filter(models.BackupActivityLog.status == status_filter.upper())
        
    activities = query.offset(skip).limit(limit).all()
    return activities

@activity_router.get(
    "/{activity_id}", 
    response_model=models.BackupActivityLogResponse,
    summary="Get a specific backup activity log by ID"
)
def get_activity_log(activity_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single backup activity log by its unique ID.
    """
    db_activity = db.query(models.BackupActivityLog).filter(models.BackupActivityLog.id == activity_id).first()
    if db_activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Activity Log not found")
    return db_activity

@activity_router.patch(
    "/{activity_id}", 
    response_model=models.BackupActivityLogResponse,
    summary="Update an existing backup activity log"
)
def update_activity_log(activity_id: UUID, activity: models.BackupActivityLogUpdate, db: Session = Depends(get_db)):
    """
    Updates the details of an existing backup activity log, typically used by the worker 
    to mark a backup as SUCCESS or FAILED and record the end time/duration.
    """
    db_activity = db.query(models.BackupActivityLog).filter(models.BackupActivityLog.id == activity_id).first()
    if db_activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Activity Log not found")

    update_data = activity.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_activity, key, value)

    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    logger.info(f"Updated activity log: {activity_id}")
    return db_activity

@activity_router.delete(
    "/{activity_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a backup activity log"
)
def delete_activity_log(activity_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a specific backup activity log entry.
    """
    db_activity = db.query(models.BackupActivityLog).filter(models.BackupActivityLog.id == activity_id).first()
    if db_activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup Activity Log not found")

    db.delete(db_activity)
    db.commit()
    logger.info(f"Deleted activity log: {activity_id}")
    return {"ok": True}

# Include the activity router under the main router's prefix for logical grouping
# Note: In a real application, you might want to mount this separately or use a nested path like /jobs/{job_id}/activities
# For simplicity and clear separation, we keep them as separate top-level routers here.
# The main application will need to include both: app.include_router(router) and app.include_router(activity_router)
# However, for this task, we will just export the main router and assume the activity router is also part of the service.
# For the purpose of a single router file, we will export a list of routers or just the main one.
# Let's just use the main router and include the activity endpoints under a logical path if needed, 
# but since the prompt asks for a complete router.py, I will combine them for simplicity.

# For the final output, I will export a list of routers to be included in the main app.
all_routers = [router, activity_router]
