import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .config import get_db
from .models import (
    Document, DocumentActivityLog, DocumentStatus, ActivityType,
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentSimpleResponse,
    DocumentActivityLogCreate, DocumentActivityLogResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["document-processing"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (CRUD Logic) ---

def get_document_by_id(db: Session, document_id: int) -> Document:
    """Fetches a document by ID or raises a 404 error."""
    document = db.get(Document, document_id)
    if not document:
        logger.warning(f"Document with ID {document_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    return document

def create_activity_log(db: Session, document_id: int, activity_type: ActivityType, details: Optional[str] = None):
    """Creates and commits a new activity log entry."""
    log_data = DocumentActivityLogCreate(
        document_id=document_id,
        activity_type=activity_type,
        details=details
    )
    db_log = DocumentActivityLog(**log_data.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

# --- Document Endpoints (CRUD) ---

@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document entry"
)
def create_document(
    document: DocumentCreate,
    db: Session = Depends(get_db)
):
    """
    Registers a new document in the system. This typically happens after a file 
    has been successfully uploaded to a storage service.
    """
    try:
        db_document = Document(**document.model_dump(exclude_unset=True))
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        
        # Log the initial upload activity
        create_activity_log(db, db_document.id, ActivityType.UPLOAD, details=f"File uploaded: {db_document.filename}")
        
        logger.info(f"Document created with ID: {db_document.id}")
        return db_document
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the document"
        )

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Retrieve a document by ID with all activity logs"
)
def read_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieves the full details of a document, including its complete history 
    of activity logs.
    """
    document = get_document_by_id(db, document_id)
    return document

@router.get(
    "/",
    response_model=List[DocumentSimpleResponse],
    summary="List all documents with simple details"
)
def list_documents(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[DocumentStatus] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of documents. Can be filtered by status.
    """
    query = select(Document).offset(skip).limit(limit)
    if status_filter:
        query = query.where(Document.status == status_filter)
        
    documents = db.scalars(query).all()
    return documents

@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata or status"
)
def update_document(
    document_id: int,
    document_update: DocumentUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates fields of an existing document. Only non-null fields in the request 
    will be updated.
    """
    db_document = get_document_by_id(db, document_id)
    
    update_data = document_update.model_dump(exclude_unset=True)
    
    # Check if status is being updated to log the change
    if "status" in update_data and update_data["status"] != db_document.status:
        old_status = db_document.status
        new_status = update_data["status"]
        create_activity_log(
            db, 
            document_id, 
            ActivityType.STATUS_UPDATE, 
            details=f"Status changed from {old_status.value} to {new_status.value}"
        )
        
    for key, value in update_data.items():
        setattr(db_document, key, value)
        
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    logger.info(f"Document ID {document_id} updated.")
    return db_document

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document"
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Deletes a document and all associated activity logs.
    """
    db_document = get_document_by_id(db, document_id)
    
    db.delete(db_document)
    db.commit()
    
    logger.info(f"Document ID {document_id} deleted.")
    return

# --- Business Logic Endpoints ---

@router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
    summary="Initiate the document processing workflow"
)
def initiate_processing(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Starts the automated processing workflow for a document. 
    This sets the status to PROCESSING and logs the event.
    """
    db_document = get_document_by_id(db, document_id)
    
    if db_document.status in [DocumentStatus.PROCESSING, DocumentStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is already in {db_document.status.value} state."
        )
        
    # Update status
    db_document.status = DocumentStatus.PROCESSING
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    # Log activity
    create_activity_log(
        db, 
        document_id, 
        ActivityType.PROCESSING_START, 
        details="Automated processing workflow initiated."
    )
    
    logger.info(f"Processing initiated for Document ID: {document_id}")
    return db_document

@router.post(
    "/{document_id}/ocr-result",
    response_model=DocumentResponse,
    summary="Record OCR extraction result and update status"
)
def record_ocr_result(
    document_id: int,
    ocr_data: dict, # Simplified payload for OCR result
    db: Session = Depends(get_db)
):
    """
    Endpoint for an external OCR service to post its results. 
    Updates the document status and logs the extracted data.
    """
    db_document = get_document_by_id(db, document_id)
    
    # Update status
    db_document.status = DocumentStatus.OCR_COMPLETED
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    # Log activity
    create_activity_log(
        db, 
        document_id, 
        ActivityType.OCR_EXTRACTION, 
        details=f"OCR extracted {len(ocr_data)} fields."
    )
    
    logger.info(f"OCR result recorded for Document ID: {document_id}")
    return db_document

# --- Activity Log Endpoints (Read-only for a specific document) ---

@router.get(
    "/{document_id}/logs",
    response_model=List[DocumentActivityLogResponse],
    summary="Get all activity logs for a specific document"
)
def get_document_logs(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieves the chronological list of all activities performed on a document.
    """
    # Ensure document exists
    get_document_by_id(db, document_id)
    
    logs = db.scalars(
        select(DocumentActivityLog)
        .where(DocumentActivityLog.document_id == document_id)
        .order_by(DocumentActivityLog.timestamp)
    ).all()
    
    return logs
