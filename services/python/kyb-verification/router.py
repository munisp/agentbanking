import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import get_db
from .models import (
    KybVerification,
    KybVerificationActivityLog,
    KybVerificationActivityLogCreate,
    KybVerificationCreate,
    KybVerificationResponse,
    KybVerificationUpdate,
    VerificationStatus,
)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router Setup ---
router = APIRouter(
    prefix="/kyb-verifications",
    tags=["KYB Verifications"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (CRUD Logic) ---

def get_verification_by_id(db: Session, verification_id: uuid.UUID) -> KybVerification:
    """Fetches a KYB verification record by its ID, raising 404 if not found."""
    verification = (
        db.query(KybVerification)
        .filter(KybVerification.id == verification_id)
        .first()
    )
    if not verification:
        logger.warning(f"Verification not found: {verification_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYB Verification with ID {verification_id} not found",
        )
    return verification

# --- Endpoints ---

@router.post(
    "/",
    response_model=KybVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new KYB Verification record",
    description="Creates a new Know Your Business (KYB) verification record for a business entity.",
)
def create_verification(
    verification_in: KybVerificationCreate, db: Session = Depends(get_db)
):
    """
    Handles the creation of a new KYB verification record.
    """
    logger.info(f"Attempting to create new verification for business: {verification_in.business_id}")
    
    # Check for existing record with the same registration number
    existing_verification = db.query(KybVerification).filter(
        KybVerification.registration_number == verification_in.registration_number
    ).first()
    
    if existing_verification:
        logger.warning(f"Verification already exists for registration number: {verification_in.registration_number}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification record already exists for registration number: {verification_in.registration_number}",
        )

    db_verification = KybVerification(**verification_in.model_dump())
    db.add(db_verification)
    db.commit()
    db.refresh(db_verification)
    logger.info(f"Successfully created verification with ID: {db_verification.id}")
    return db_verification


@router.get(
    "/",
    response_model=List[KybVerificationResponse],
    summary="List all KYB Verification records",
    description="Retrieves a list of all KYB verification records, with optional filtering and pagination.",
)
def list_verifications(
    status_filter: Optional[VerificationStatus] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Retrieves a list of KYB verification records, optionally filtered by status.
    """
    query = db.query(KybVerification)
    
    if status_filter:
        query = query.filter(KybVerification.status == status_filter.value)
        
    verifications = query.limit(limit).offset(offset).all()
    return verifications


@router.get(
    "/{verification_id}",
    response_model=KybVerificationResponse,
    summary="Get a specific KYB Verification record",
    description="Retrieves the details of a single KYB verification record by its unique ID.",
)
def read_verification(
    verification_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    Retrieves a single KYB verification record by ID.
    """
    return get_verification_by_id(db, verification_id)


@router.patch(
    "/{verification_id}",
    response_model=KybVerificationResponse,
    summary="Update a KYB Verification record",
    description="Updates the status or other mutable fields of an existing KYB verification record.",
)
def update_verification(
    verification_id: uuid.UUID,
    verification_in: KybVerificationUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing KYB verification record.
    """
    db_verification = get_verification_by_id(db, verification_id)
    
    update_data = verification_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_verification, key, value)
        
    db.add(db_verification)
    db.commit()
    db.refresh(db_verification)
    logger.info(f"Updated verification with ID: {verification_id}")
    return db_verification


@router.delete(
    "/{verification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a KYB Verification record",
    description="Deletes a KYB verification record and all associated activity logs.",
)
def delete_verification(
    verification_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    Deletes a KYB verification record.
    """
    db_verification = get_verification_by_id(db, verification_id)
    
    db.delete(db_verification)
    db.commit()
    logger.info(f"Deleted verification with ID: {verification_id}")
    return {"ok": True}


# --- Business-Specific Endpoints ---

@router.post(
    "/{verification_id}/log",
    response_model=models.KybVerificationActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity log entry to a verification record",
    description="Adds a new entry to the activity log for a specific KYB verification record.",
)
def add_activity_log(
    verification_id: uuid.UUID,
    log_in: KybVerificationActivityLogCreate,
    db: Session = Depends(get_db),
):
    """
    Adds an activity log entry to a KYB verification record.
    """
    db_verification = get_verification_by_id(db, verification_id)
    
    db_log = KybVerificationActivityLog(
        verification_id=verification_id,
        **log_in.model_dump()
    )
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Added activity log to verification ID: {verification_id}")
    return db_log


@router.patch(
    "/{verification_id}/status",
    response_model=KybVerificationResponse,
    summary="Update the status of a KYB Verification record",
    description="A dedicated endpoint to quickly update only the status of a KYB verification record.",
)
def update_verification_status(
    verification_id: uuid.UUID,
    new_status: VerificationStatus,
    actor: str,
    db: Session = Depends(get_db),
):
    """
    Updates the status of a KYB verification record and automatically logs the change.
    """
    db_verification = get_verification_by_id(db, verification_id)
    
    old_status = db_verification.status
    
    if old_status == new_status.value:
        logger.info(f"Status for {verification_id} is already {new_status.value}. No change made.")
        return db_verification
        
    # Update status
    db_verification.status = new_status.value
    
    # Create activity log entry for status change
    log_details = f"Status changed from {old_status} to {new_status.value}"
    db_log = KybVerificationActivityLog(
        verification_id=verification_id,
        actor=actor,
        action="STATUS_CHANGE",
        details=log_details,
    )
    
    db.add(db_verification)
    db.add(db_log)
    db.commit()
    db.refresh(db_verification)
    logger.info(f"Status for {verification_id} changed to {new_status.value} by {actor}")
    return db_verification
