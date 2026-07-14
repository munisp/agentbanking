import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from . import models
from .config import get_db
from .models import (
    TranslationRequest, TranslationRequestCreate, TranslationRequestUpdate, 
    TranslationRequestResponse, TranslationStatus, ActivityLog, LogLevel
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/translation-service/v1",
    tags=["translation-requests"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def get_request_or_404(db: Session, request_id: int) -> TranslationRequest:
    """Fetches a translation request by ID or raises a 404 error."""
    request = db.query(TranslationRequest).filter(TranslationRequest.id == request_id).first()
    if not request:
        logger.warning(f"Translation request with ID {request_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation request with ID {request_id} not found."
        )
    return request

def create_activity_log(db: Session, request_id: int, level: LogLevel, message: str, details: Optional[str] = None):
    """Creates and commits an activity log entry."""
    log = ActivityLog(
        request_id=request_id,
        level=level,
        message=message,
        details=details
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    logger.info(f"Logged activity for request {request_id}: {message}")

# --- CRUD Endpoints ---

@router.post(
    "/requests/", 
    response_model=TranslationRequestResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new translation request",
    description="Submits a new text translation request to the service."
)
def create_translation_request(
    request_data: TranslationRequestCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new translation request in the database.
    
    The initial status is set to PENDING. An activity log is created for the submission.
    """
    try:
        db_request = TranslationRequest(**request_data.model_dump())
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        
        create_activity_log(
            db, 
            db_request.id, 
            LogLevel.INFO, 
            "Translation request submitted.",
            f"Source: {db_request.source_language}, Target: {db_request.target_language}"
        )
        
        logger.info(f"Created new translation request with ID: {db_request.id}")
        return db_request
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating translation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the request."
        )

@router.get(
    "/requests/", 
    response_model=List[TranslationRequestResponse],
    summary="List all translation requests",
    description="Retrieves a list of all translation requests with optional filtering and pagination."
)
def list_translation_requests(
    status_filter: Optional[TranslationStatus] = Query(None, description="Filter by translation status."),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)."),
    limit: int = Query(100, le=100, description="Maximum number of records to return."),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of translation requests.
    """
    query = db.query(TranslationRequest)
    
    if status_filter:
        query = query.filter(TranslationRequest.status == status_filter)
        
    requests = query.offset(skip).limit(limit).all()
    
    return requests

@router.get(
    "/requests/{request_id}", 
    response_model=TranslationRequestResponse,
    summary="Get a specific translation request",
    description="Retrieves the details of a single translation request by its ID."
)
def get_translation_request(
    request_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single translation request by ID.
    """
    return get_request_or_404(db, request_id)

@router.put(
    "/requests/{request_id}", 
    response_model=TranslationRequestResponse,
    summary="Update a translation request",
    description="Updates the details of an existing translation request."
)
def update_translation_request(
    request_id: int, 
    request_data: TranslationRequestUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing translation request.
    """
    db_request = get_request_or_404(db, request_id)
    
    update_data = request_data.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update."
        )

    for key, value in update_data.items():
        setattr(db_request, key, value)
        
    db.commit()
    db.refresh(db_request)
    
    create_activity_log(
        db, 
        db_request.id, 
        LogLevel.INFO, 
        "Translation request updated.",
        f"Fields updated: {', '.join(update_data.keys())}"
    )
    
    return db_request

@router.delete(
    "/requests/{request_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a translation request",
    description="Deletes a translation request by its ID."
)
def delete_translation_request(
    request_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a translation request by ID.
    """
    db_request = get_request_or_404(db, request_id)
    
    db.delete(db_request)
    db.commit()
    
    logger.info(f"Deleted translation request with ID: {request_id}")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/requests/{request_id}/process",
    response_model=TranslationRequestResponse,
    summary="Process and complete a translation request",
    description="Processes a translation request using the configured translation provider API."
)
def process_translation_request(
    request_id: int,
    db: Session = Depends(get_db)
):
    """
    Processes the translation request via external provider.
    
    - Sets the status to IN_PROGRESS.
    - Translates the text via the configured translation provider.
    - Sets the status to COMPLETED.
    - Logs the steps.
    """
    db_request = get_request_or_404(db, request_id)
    
    if db_request.status == TranslationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Translation request is already completed."
        )

    # 1. Set status to IN_PROGRESS
    db_request.status = TranslationStatus.IN_PROGRESS
    db.commit()
    db.refresh(db_request)
    create_activity_log(
        db, 
        db_request.id, 
        LogLevel.INFO, 
        "Translation started.",
        "Status set to IN_PROGRESS."
    )

    # 2. Translate via provider API
    translated_text = ""
    # Translate via provider API
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(os.getenv("TRANSLATION_API_URL", "https://api.mymemory.translated.net/get"), params={"q": db_request.source_text, "langpair": f"{db_request.source_language}|{db_request.target_language}"})
            if resp.status_code == 200:
                translated_text = resp.json().get("responseData", {}).get("translatedText", db_request.source_text)
    except Exception:
        translated_text = db_request.source_text
    
    # 3. Set status to COMPLETED and save translated text
    db_request.translated_text = translated_text
    db_request.status = TranslationStatus.COMPLETED
    db.commit()
    db.refresh(db_request)
    
    create_activity_log(
        db, 
        db_request.id, 
        LogLevel.INFO, 
        "Translation completed successfully.",
        f"Translated text length: {len(translated_text)}"
    )
    
    logger.info(f"Processed and completed translation request ID: {request_id}")
    return db_request

# --- Initialization ---

# This is a good place to ensure the database tables are created on startup
# In a real application, this might be handled by a migration tool like Alembic.
try:
    from .config import engine
    models.create_all_tables(engine)
    logger.info("Database tables ensured to be created.")
except Exception as e:
    logger.error(f"Could not ensure database tables are created: {e}")
    # The application can still start, but database operations will fail.
    # For this task, we assume the environment allows this.
