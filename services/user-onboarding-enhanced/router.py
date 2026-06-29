from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from service import OnboardingService, UserOnboardingException, UserNotFound, EmailAlreadyExists, InvalidOnboardingStep, DocumentNotFound
from schemas import UserCreate, User, KYCProfileCreate, KYCProfile, DocumentUpload, Document, StatusResponse, DocumentUpdateStatus, UserUpdate
from models import OnboardingStatus

# --- Authentication Dependency (Placeholder) ---
# In a real application, this would be a proper dependency that checks for a valid JWT/API Key
# For simplicity, we'll use a placeholder function that always returns a user ID (e.g., 1)
def get_current_user_id(user_id: int = 1) -> int:
    """Placeholder for an actual authentication dependency."""
    return user_id

# --- Router Setup ---
router = APIRouter()

# --- Exception Handling Utility ---
def handle_service_exception(e: UserOnboardingException) -> None:
    """Converts a service exception into an HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Endpoints ---

# --- Step 1: User Registration (Create) ---
@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED, summary="Step 1: Register User and Start Onboarding")
def register_user(user_data: UserCreate, db: Session = Depends(get_db)) -> None:
    """
    Registers a new user and initiates the enhanced onboarding process.
    """
    try:
        service = OnboardingService(db)
        new_user = service.create_user(user_data)
        return new_user
    except EmailAlreadyExists as e:
        handle_service_exception(e)
    except UserOnboardingException as e:
        handle_service_exception(e)

# --- Read Operations (User Management) ---
@router.get("/users/{user_id}", response_model=User, summary="Get User Details (Read)")
def get_user_details(user_id: int, db: Session = Depends(get_db)) -> None:
    """
    Retrieves a user's details, including their KYC profile and documents.
    """
    try:
        service = OnboardingService(db)
        return service.get_user_with_relations(user_id)
    except UserNotFound as e:
        handle_service_exception(e)

@router.get("/users", response_model=List[User], summary="List All Users (List)")
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)) -> None:
    """
    Retrieves a list of all users.
    """
    service = OnboardingService(db)
    return service.get_all_users(skip=skip, limit=limit)

# --- Update Operations (User Management) ---
@router.put("/users/{user_id}", response_model=User, summary="Update User Details (Update)")
def update_user_details(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)) -> None:
    """
    Updates a user's basic information.
    """
    try:
        service = OnboardingService(db)
        return service.update_user(user_id, user_data)
    except UserNotFound as e:
        handle_service_exception(e)

# --- Delete Operations (User Management) ---
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete User (Delete)")
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Deletes a user and all associated onboarding data.
    """
    try:
        service = OnboardingService(db)
        service.delete_user(user_id)
        return {"message": "User deleted successfully"}
    except UserNotFound as e:
        handle_service_exception(e)

# --- Step 2: KYC Profile Submission ---
@router.post("/{user_id}/kyc", response_model=KYCProfile, summary="Step 2: Submit KYC Identity Information")
def submit_kyc_profile(user_id: int, kyc_data: KYCProfileCreate, db: Session = Depends(get_db)) -> None:
    """
    Submits the user's identity information (KYC).
    """
    try:
        service = OnboardingService(db)
        return service.create_kyc_profile(user_id, kyc_data)
    except (UserNotFound, InvalidOnboardingStep) as e:
        handle_service_exception(e)

# --- Step 3: Document Upload ---
@router.post("/{user_id}/documents", response_model=Document, summary="Step 3: Upload Document for Verification")
def upload_document(user_id: int, doc_data: DocumentUpload, db: Session = Depends(get_db)) -> None:
    """
    Uploads a document (e.g., Passport, Utility Bill) for verification.
    The file_path should be a secure URL to the stored file.
    """
    try:
        service = OnboardingService(db)
        return service.upload_document(user_id, doc_data)
    except (UserNotFound, InvalidOnboardingStep) as e:
        handle_service_exception(e)

@router.get("/{user_id}/documents", response_model=List[Document], summary="Get All Uploaded Documents")
def get_uploaded_documents(user_id: int, db: Session = Depends(get_db)) -> None:
    """
    Retrieves a list of all documents uploaded by the user.
    """
    try:
        service = OnboardingService(db)
        return service.get_documents(user_id)
    except UserNotFound as e:
        handle_service_exception(e)

# --- Step 4: Verification (Admin/Internal Endpoint) ---
@router.patch("/documents/{document_id}/status", response_model=Document, summary="Step 4: Update Document Verification Status (Admin)")
def update_document_verification_status(document_id: int, status_data: DocumentUpdateStatus, db: Session = Depends(get_db), admin_user_id: int = Depends(get_current_user_id)) -> None:
    """
    Updates the verification status of a specific document. This is typically an internal/admin endpoint.
    """
    try:
        service = OnboardingService(db)
        return service.update_document_status(document_id, status_data)
    except DocumentNotFound as e:
        handle_service_exception(e)

# --- Step 5: Final Completion ---
@router.post("/{user_id}/complete", response_model=StatusResponse, summary="Step 5: Finalize Onboarding")
def finalize_onboarding(user_id: int, db: Session = Depends(get_db)) -> None:
    """
    Finalizes the onboarding process after all verification steps are successful.
    """
    try:
        service = OnboardingService(db)
        user = service.complete_onboarding(user_id)
        return StatusResponse(
            message=f"Onboarding successfully completed for user ID {user_id}.",
            status=user.onboarding_status
        )
    except (UserNotFound, InvalidOnboardingStep) as e:
        handle_service_exception(e)

# --- Utility Endpoint ---
@router.get("/{user_id}/status", response_model=StatusResponse, summary="Get Current Onboarding Status")
def get_onboarding_status(user_id: int, db: Session = Depends(get_db)) -> None:
    """
    Retrieves the current onboarding status of a user.
    """
    try:
        service = OnboardingService(db)
        user = service.get_user(user_id)
        return StatusResponse(
            message=f"Current status for user ID {user_id}.",
            status=user.onboarding_status
        )
    except UserNotFound as e:
        handle_service_exception(e)