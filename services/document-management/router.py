import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from . import models
from .config import get_db, settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(settings.SERVICE_NAME)

router = APIRouter(
    prefix="/documents",
    tags=["document-management"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(db: Session, document_id: uuid.UUID, action: str, details: Optional[str] = None):
    """Logs an activity for a specific document."""
    log_entry = models.DocumentActivityLog(
        document_id=document_id,
        action=action,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Document {document_id} activity logged: {action}")

def get_document_or_404(db: Session, document_id: uuid.UUID) -> models.Document:
    """Fetches a document by ID or raises a 404 error."""
    document = db.get(models.Document, document_id)
    if not document:
        logger.warning(f"Document with ID {document_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    return document

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.DocumentResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new document record"
)
def create_document(
    document_in: models.DocumentCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new document record in the database.
    
    The `file_path` should point to the actual storage location of the document.
    """
    db_document = models.Document(**document_in.model_dump())
    
    try:
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        
        # Log creation activity
        log_activity(db, db_document.id, "CREATED", f"Initial status: {db_document.status}")
        
        logger.info(f"Document created with ID: {db_document.id}")
        return db_document
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create document"
        )

@router.get(
    "/{document_id}", 
    response_model=models.DocumentWithLogsResponse,
    summary="Retrieve a document by ID with its activity logs"
)
def read_document(
    document_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single document by its unique ID, including all associated activity logs.
    """
    document = get_document_or_404(db, document_id)
    
    # Eagerly load activity logs for the response model
    document_with_logs = db.execute(
        select(models.Document)
        .where(models.Document.id == document_id)
        .options(models.selectinload(models.Document.activity_logs))
    ).scalar_one_or_none()
    
    return document_with_logs

@router.get(
    "/", 
    response_model=List[models.DocumentResponse],
    summary="List all documents with optional filtering and pagination"
)
def list_documents(
    owner_id: Optional[int] = Query(None, description="Filter by document owner ID"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by document status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of documents, supporting filtering by owner, type, and status.
    """
    offset = (page - 1) * size
    
    stmt = select(models.Document)
    
    if owner_id is not None:
        stmt = stmt.where(models.Document.owner_id == owner_id)
    if document_type:
        stmt = stmt.where(models.Document.document_type == document_type)
    if status_filter:
        stmt = stmt.where(models.Document.status == status_filter)
        
    documents = db.scalars(stmt.offset(offset).limit(size)).all()
    
    return documents

@router.patch(
    "/{document_id}", 
    response_model=models.DocumentResponse,
    summary="Update an existing document record"
)
def update_document(
    document_id: uuid.UUID, 
    document_in: models.DocumentUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates fields of an existing document record.
    """
    db_document = get_document_or_404(db, document_id)
    
    update_data = document_in.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    for key, value in update_data.items():
        setattr(db_document, key, value)
        
    db_document.updated_at = func.now() # Explicitly update timestamp
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    # Log update activity
    log_activity(db, db_document.id, "UPDATED", f"Fields updated: {', '.join(update_data.keys())}")
    
    logger.info(f"Document {document_id} updated.")
    return db_document

@router.delete(
    "/{document_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document record"
)
def delete_document(
    document_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    """
    Deletes a document record from the database.
    Associated activity logs are deleted automatically via CASCADE.
    """
    db_document = get_document_or_404(db, document_id)
    
    db.delete(db_document)
    db.commit()
    
    # Log deletion activity (must happen before commit if log was in a separate table without cascade)
    # Since logs are cascaded, we log the action before the document is gone.
    logger.info(f"Document {document_id} deleted.")
    return

# --- Business Logic Endpoints ---

@router.post(
    "/{document_id}/verify",
    response_model=models.DocumentResponse,
    summary="Trigger document verification process"
)
def verify_document(
    document_id: uuid.UUID,
    is_valid: bool = Query(..., description="Set the verification result (True for VERIFIED, False for REJECTED)"),
    db: Session = Depends(get_db)
):
    """
    Triggers an external process to verify the document content.
    Updates the document status based on the verification result.
    """
    db_document = get_document_or_404(db, document_id)
    
    new_status = "VERIFIED" if is_valid else "REJECTED"
    action = "VERIFIED_SUCCESS" if is_valid else "VERIFIED_FAILURE"
    
    if db_document.status == new_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is already in status: {new_status}"
        )

    db_document.status = new_status
    db_document.updated_at = func.now()
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    log_activity(db, db_document.id, action, f"Document status changed to {new_status} after verification.")
    
    logger.info(f"Document {document_id} verification complete. New status: {new_status}")
    return db_document
