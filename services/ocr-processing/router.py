import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import requests

from . import models
from .config import get_db, get_settings
from .models import OCRResult, OCRActivityLog, OCRStatus
from .models import (
    OCRResultCreate, OCRResultUpdate, OCRResultResponse, 
    OCRResultFullResponse, OCRActivityLogResponse
)

# --- Configuration and Logging ---
settings = get_settings()
router = APIRouter(prefix="/ocr-processing", tags=["ocr-processing"])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Helper Functions ---

def create_log_entry(db: Session, ocr_result_id: int, activity_type: str, details: dict = None) -> models.OCRActivityLog:
    """Creates and adds an activity log entry to the database."""
    log_entry = OCRActivityLog(
        ocr_result_id=ocr_result_id,
        activity_type=activity_type,
        details=details or {}
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=OCRResultResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new file for OCR processing."
)
def create_ocr_job(
    ocr_job: OCRResultCreate, 
    db: Session = Depends(get_db)
):
    """
    Submits a new file path for asynchronous OCR processing.
    The initial status is set to PENDING.
    """
    logger.info(f"Creating new OCR job for file: {ocr_job.file_name}")
    try:
        db_ocr_job = OCRResult(**ocr_job.model_dump())
        db.add(db_ocr_job)
        db.commit()
        db.refresh(db_ocr_job)
        
        create_log_entry(db, db_ocr_job.id, "SUBMISSION", {"file_path": ocr_job.file_path})
        
        return db_ocr_job
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating OCR job: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create OCR job due to data integrity issue."
        )

@router.get(
    "/{ocr_id}", 
    response_model=OCRResultFullResponse,
    summary="Retrieve a specific OCR job result and its activity logs."
)
def read_ocr_job(
    ocr_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves the details of a single OCR job, including its full history of activity logs.
    """
    db_ocr_job = db.query(OCRResult).filter(OCRResult.id == ocr_id).first()
    if db_ocr_job is None:
        logger.warning(f"OCR job with ID {ocr_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"OCR job with ID {ocr_id} not found"
        )
    return db_ocr_job

@router.get(
    "/", 
    response_model=List[OCRResultResponse],
    summary="List all OCR jobs with optional filtering."
)
def list_ocr_jobs(
    status_filter: OCRStatus = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all OCR jobs, paginated and optionally filtered by status.
    """
    query = db.query(OCRResult)
    if status_filter:
        query = query.filter(OCRResult.status == status_filter)
        
    ocr_jobs = query.offset(skip).limit(limit).all()
    return ocr_jobs

@router.put(
    "/{ocr_id}", 
    response_model=OCRResultResponse,
    summary="Update the status or results of an existing OCR job."
)
def update_ocr_job(
    ocr_id: int, 
    ocr_update: OCRResultUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates the status, extracted text, or metadata of an OCR job. 
    This endpoint is typically used by the background OCR worker service.
    """
    db_ocr_job = db.query(OCRResult).filter(OCRResult.id == ocr_id).first()
    if db_ocr_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"OCR job with ID {ocr_id} not found"
        )

    update_data = ocr_update.model_dump(exclude_unset=True)
    
    if "status" in update_data and update_data["status"] != db_ocr_job.status:
        create_log_entry(db, ocr_id, "STATUS_CHANGE", {"old_status": db_ocr_job.status.value, "new_status": update_data["status"].value})
        logger.info(f"OCR job {ocr_id} status changed from {db_ocr_job.status} to {update_data['status']}")

    for key, value in update_data.items():
        setattr(db_ocr_job, key, value)

    db.commit()
    db.refresh(db_ocr_job)
    return db_ocr_job

@router.delete(
    "/{ocr_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an OCR job and all associated logs."
)
def delete_ocr_job(
    ocr_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes an OCR job record permanently.
    """
    db_ocr_job = db.query(OCRResult).filter(OCRResult.id == ocr_id).first()
    if db_ocr_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"OCR job with ID {ocr_id} not found"
        )

    db.delete(db_ocr_job)
    db.commit()
    logger.info(f"OCR job with ID {ocr_id} deleted successfully.")
    return

# --- Business Logic Endpoint ---

@router.post(
    "/{ocr_id}/process",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger the external OCR engine for a specific job."
)
def trigger_ocr_processing(
    ocr_id: int,
    db: Session = Depends(get_db)
):
    """
    Triggers the external OCR engine service to process the file associated with the given job ID.
    This processs an asynchronous call to a worker service.
    """
    db_ocr_job = db.query(OCRResult).filter(OCRResult.id == ocr_id).first()
    if db_ocr_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"OCR job with ID {ocr_id} not found"
        )

    if db_ocr_job.status in [OCRStatus.PROCESSING, OCRStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"OCR job is already in status: {db_ocr_job.status.value}"
        )

    # 1. Update status to PROCESSING
    db_ocr_job.status = OCRStatus.PROCESSING
    db.commit()
    create_log_entry(db, ocr_id, "STATUS_CHANGE", {"old_status": db_ocr_job.status.value, "new_status": OCRStatus.PROCESSING.value})
    
    # 2. Call external OCR service (processed)
    try:
        payload = {
            "job_id": ocr_id,
            "file_path": db_ocr_job.file_path,
            "file_name": db_ocr_job.file_name
        }
        
        # In a real application, this would be a non-blocking message queue push (e.g., Celery, Kafka)
        # or a non-blocking HTTP call to a worker service. Here, we process the HTTP call.
        response = requests.post(
            settings.OCR_ENGINE_URL, 
            json=payload, 
            timeout=settings.OCR_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        
        logger.info(f"Successfully triggered external OCR service for job {ocr_id}.")
        create_log_entry(db, ocr_id, "TRIGGER_SUCCESS", {"engine_url": settings.OCR_ENGINE_URL})
        
        return {"message": "OCR processing triggered successfully.", "job_id": ocr_id}

    except requests.exceptions.RequestException as e:
        # 3. Handle failure to trigger
        db_ocr_job.status = OCRStatus.RETRY
        db.commit()
        create_log_entry(db, ocr_id, "TRIGGER_FAILURE", {"error": str(e), "engine_url": settings.OCR_ENGINE_URL})
        logger.error(f"Failed to trigger external OCR service for job {ocr_id}: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to communicate with the external OCR engine: {e}"
        )
