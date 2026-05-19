import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .config import get_db
from .models import (
    ActivityType, OcrJob, OcrJobActivityLog, OcrJobCreate, OcrJobResponse,
    OcrJobStatus, OcrJobUpdate
)

# --- Configuration and Setup ---

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastAPI router
router = APIRouter(
    prefix="/ocr_jobs",
    tags=["OCR Jobs"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(db: Session, job_id: uuid.UUID, activity_type: ActivityType, details: str, metadata_json: Optional[dict] = None):
    """
    Creates a new activity log entry for a given OCR job.
    """
    log_entry = OcrJobActivityLog(
        job_id=job_id,
        activity_type=activity_type,
        details=details,
        metadata_json=metadata_json
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Job {job_id}: Logged activity {activity_type.value} - {details}")

def get_job_or_404(db: Session, job_id: uuid.UUID) -> OcrJob:
    """
    Retrieves an OcrJob by ID or raises a 404 HTTPException.
    """
    job = db.query(OcrJob).filter(OcrJob.id == job_id).first()
    if not job:
        logger.warning(f"Attempted access to non-existent job: {job_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OCR Job with ID {job_id} not found"
        )
    return job

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=OcrJobResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new OCR job"
)
def create_ocr_job(job_in: OcrJobCreate, db: Session = Depends(get_db)):
    """
    Submits a new file for multi-engine OCR processing.
    
    The job is created with a PENDING status and is ready to be picked up by a worker.
    """
    db_job = OcrJob(
        file_url=job_in.file_url,
        ocr_engine=job_in.ocr_engine,
        status=OcrJobStatus.PENDING
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    log_activity(
        db, 
        db_job.id, 
        ActivityType.CREATED, 
        f"Job created for file: {job_in.file_url} using engine: {job_in.ocr_engine.value}"
    )
    
    logger.info(f"New OCR job created with ID: {db_job.id}")
    return db_job

@router.get(
    "/{job_id}", 
    response_model=OcrJobResponse,
    summary="Retrieve a specific OCR job"
)
def read_ocr_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Fetches the details of a single OCR job, including its activity history.
    """
    db_job = get_job_or_404(db, job_id)
    return db_job

@router.get(
    "/", 
    response_model=List[OcrJobResponse],
    summary="List all OCR jobs"
)
def list_ocr_jobs(
    status_filter: Optional[OcrJobStatus] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of OCR jobs with optional filtering by status and pagination.
    """
    query = db.query(OcrJob)
    if status_filter:
        query = query.filter(OcrJob.status == status_filter)
        
    jobs = query.offset(skip).limit(limit).all()
    return jobs

@router.patch(
    "/{job_id}", 
    response_model=OcrJobResponse,
    summary="Update an existing OCR job"
)
def update_ocr_job(job_id: uuid.UUID, job_in: OcrJobUpdate, db: Session = Depends(get_db)):
    """
    Updates the status, results, or other properties of an OCR job.
    This is typically used by worker processes to report progress or final results.
    """
    db_job = get_job_or_404(db, job_id)
    
    update_data = job_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_job, key, value)
        
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    log_activity(
        db, 
        db_job.id, 
        ActivityType.STATUS_UPDATE, 
        f"Job updated. New status: {db_job.status.value}"
    )
    
    logger.info(f"OCR job {job_id} updated.")
    return db_job

@router.delete(
    "/{job_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an OCR job"
)
def delete_ocr_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes an OCR job and all associated activity logs.
    """
    db_job = get_job_or_404(db, job_id)
    
    db.delete(db_job)
    db.commit()
    
    logger.info(f"OCR job {job_id} deleted.")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{job_id}/process",
    response_model=OcrJobResponse,
    summary="Process an OCR job"
)
def process_ocr_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Processes the start of the OCR processing workflow for a PENDING job.
    
    In a real-world scenario, this would trigger an asynchronous worker process.
    For this API, it simply updates the status to PROCESSING.
    """
    db_job = get_job_or_404(db, job_id)
    
    if db_job.status != OcrJobStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is already in status: {db_job.status.value}. Only PENDING jobs can be processed."
        )
        
    # Start OCR processing
    db_job.status = OcrJobStatus.PROCESSING
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    log_activity(
        db, 
        db_job.id, 
        ActivityType.STATUS_UPDATE, 
        "Processing started by worker."
    )
    
    logger.info(f"OCR job {job_id} processing initiated.")
    return db_job

@router.post(
    "/{job_id}/complete",
    response_model=OcrJobResponse,
    summary="Mark an OCR job as completed and add results"
)
def complete_ocr_job(
    job_id: uuid.UUID, 
    result_text: str, 
    result_json: dict, 
    db: Session = Depends(get_db)
):
    """
    Endpoint used by the worker to mark a job as COMPLETED and submit the results.
    """
    db_job = get_job_or_404(db, job_id)
    
    if db_job.status == OcrJobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already completed."
        )
        
    # Update job with results and status
    db_job.status = OcrJobStatus.COMPLETED
    db_job.result_text = result_text
    db_job.result_json = result_json
    
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    log_activity(
        db, 
        db_job.id, 
        ActivityType.RESULT_ADDED, 
        "OCR processing successfully completed and results saved."
    )
    
    logger.info(f"OCR job {job_id} completed with results.")
    return db_job
