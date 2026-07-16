import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

# Assuming config.py and models.py are in the same package/directory
from .config import get_db
from .models import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdateStatus,
    DocumentCreate,
    DocumentResponse,
    DocumentStatus,
    DocumentUpdateStatus,
    KYCApplication,
    KYCDocument,
    KYCStatus,
    KYCStatusHistory,
)

# --- Setup ---
router = APIRouter(prefix="/kyc", tags=["kyc-service"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

# --- Authentication ---
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token and return current user - REQUIRED for all endpoints"""
    if not JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET not configured - cannot authenticate"
        )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        return {"user_id": user_id, "role": payload.get("role", "user")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

def require_role(required_roles: List[str]):
    """Dependency to require specific roles for an endpoint"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {required_roles}"
            )
        return current_user
    return role_checker

# --- Helper Functions (Business Logic) ---

def _create_status_history_entry(
    db: Session, application_id: int, new_status: KYCStatus, changed_by_id: int, notes: str = None
):
    """
    Internal function to create a new status history entry.
    """
    history_entry = KYCStatusHistory(
        application_id=application_id,
        status=new_status,
        changed_by_id=changed_by_id,
        notes=notes,
    )
    db.add(history_entry)
    # The commit will happen in the main function that calls this helper

def _update_application_status(
    db: Session, application: KYCApplication, new_status: KYCStatus, reviewer_id: int, notes: str = None, rejection_reason: str = None
):
    """
    Internal function to update the application's current status and log the change.
    """
    if application.current_status == new_status:
        return

    # Log the status change
    _create_status_history_entry(
        db=db,
        application_id=application.id,
        new_status=new_status,
        changed_by_id=reviewer_id,
        notes=notes,
    )

    # Update the application fields
    application.current_status = new_status
    application.reviewer_id = reviewer_id
    application.rejection_reason = rejection_reason

    db.add(application)
    db.flush() # Flush to update the 'last_updated' timestamp before commit

# --- Endpoints: Application Management (User/Public Facing) ---

@router.post(
    "/applications/",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new KYC application",
)
def submit_kyc_application(
    application_in: ApplicationCreate, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Submits a new KYC application for a user, including initial documents.
    """
    # 1. Check if a PENDING or IN_REVIEW application already exists for the user
    existing_app = db.query(KYCApplication).filter(
        KYCApplication.user_id == application_in.user_id,
        KYCApplication.current_status.in_([KYCStatus.PENDING, KYCStatus.IN_REVIEW])
    ).first()

    if existing_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active KYC application is already pending or under review for this user.",
        )

    # 2. Create the new application
    db_application = KYCApplication(
        user_id=application_in.user_id,
        current_status=KYCStatus.PENDING,
    )
    db.add(db_application)
    db.flush() # Flush to get the application ID

    # 3. Add documents
    for doc_in in application_in.documents:
        db_document = KYCDocument(
            application_id=db_application.id,
            document_type=doc_in.document_type,
            file_url=doc_in.file_url,
            document_status=DocumentStatus.UPLOADED,
        )
        db.add(db_document)

    # 4. Create initial status history entry
    _create_status_history_entry(
        db=db,
        application_id=db_application.id,
        new_status=KYCStatus.PENDING,
        changed_by_id=application_in.user_id, # User is the one who initiated the change
        notes="Application submitted with initial documents.",
    )

    db.commit()
    db.refresh(db_application)
    return db_application


@router.get(
    "/applications/user/{user_id}",
    response_model=List[ApplicationResponse],
    summary="Get all KYC applications for a specific user",
)
def get_user_applications(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves all KYC applications associated with a given user ID.
    """
    applications = db.query(KYCApplication).filter(
        KYCApplication.user_id == user_id
    ).all()
    return applications


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
    summary="Get a specific KYC application by ID",
)
def get_application_by_id(
    application_id: int, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves a single KYC application by its ID.
    """
    application = db.query(KYCApplication).filter(
        KYCApplication.id == application_id
    ).first()
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Application with ID {application_id} not found",
        )
    return application

# --- Endpoints: Reviewer/Admin Management (Internal/Reviewer Facing) ---

@router.get(
    "/applications/review/",
    response_model=List[ApplicationResponse],
    summary="Get applications needing review",
)
def get_applications_for_review(
    db: Session = Depends(get_db), 
    limit: int = 10, 
    offset: int = 0,
    current_user: dict = Depends(require_role(["admin", "reviewer"]))
):
    """
    Retrieves a list of applications that are PENDING or IN_REVIEW.
    """
    applications = db.query(KYCApplication).filter(
        KYCApplication.current_status.in_([KYCStatus.PENDING, KYCStatus.IN_REVIEW])
    ).order_by(KYCApplication.submission_date).offset(offset).limit(limit).all()
    return applications


@router.put(
    "/applications/{application_id}/status",
    response_model=ApplicationResponse,
    summary="Update the status of a KYC application",
)
def update_application_status(
    application_id: int,
    status_update: ApplicationUpdateStatus,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["admin", "reviewer"]))
):
    """
    Allows a reviewer to change the overall status of a KYC application (e.g., APPROVE, REJECT).
    """
    application = db.query(KYCApplication).filter(
        KYCApplication.id == application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Application with ID {application_id} not found",
        )

    # Business Logic: Validation for status change
    if status_update.new_status in [KYCStatus.APPROVED, KYCStatus.REJECTED] and not status_update.reviewer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer ID is required for final status changes (APPROVED/REJECTED).",
        )

    if status_update.new_status == KYCStatus.REJECTED and not status_update.rejection_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required when rejecting an application.",
        )

    # Update status and log history
    _update_application_status(
        db=db,
        application=application,
        new_status=status_update.new_status,
        reviewer_id=status_update.reviewer_id,
        notes=status_update.notes,
        rejection_reason=status_update.rejection_reason,
    )

    db.commit()
    db.refresh(application)
    return application


@router.put(
    "/documents/{document_id}/status",
    response_model=DocumentResponse,
    summary="Update the status of a specific document",
)
def update_document_status(
    document_id: int,
    status_update: DocumentUpdateStatus,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role(["admin", "reviewer"]))
):
    """
    Allows a reviewer or an automated process (e.g., OCR) to update the status of a single document.
    """
    document = db.query(KYCDocument).filter(
        KYCDocument.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"KYC Document with ID {document_id} not found",
        )

    # Update document status and verification details
    document.document_status = status_update.document_status
    document.verification_details = status_update.verification_details
    db.add(document)
    db.flush()

    # Business Logic: Check if all documents are verified/rejected to potentially update application status
    application = document.application
    all_documents = application.documents

    # Count verified and rejected documents
    verified_count = sum(1 for doc in all_documents if doc.document_status == DocumentStatus.VERIFIED)
    rejected_count = sum(1 for doc in all_documents if doc.document_status == DocumentStatus.REJECTED)
    total_count = len(all_documents)

    # If all documents are processed (verified or rejected)
    if verified_count + rejected_count == total_count:
        if rejected_count > 0:
            # If any document is rejected, the application needs correction
            new_app_status = KYCStatus.NEEDS_CORRECTION
            notes = "One or more documents were rejected. Application requires correction."
        else:
            # If all documents are verified, the application is ready for final approval
            new_app_status = KYCStatus.IN_REVIEW
            notes = "All submitted documents have been successfully verified. Application is ready for final review."

        # Only update if the current status is PENDING or IN_REVIEW (to avoid overriding manual rejection/approval)
        if application.current_status in [KYCStatus.PENDING, KYCStatus.IN_REVIEW]:
            # Use system ID for automated process
            _update_application_status(
                db=db,
                application=application,
                new_status=new_app_status,
                reviewer_id=0, # Automated process ID
                notes=notes,
            )

    db.commit()
    db.refresh(document)
    return document
