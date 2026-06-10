from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from database import get_db
from service import KYCService, CaseNotFoundError, CaseAlreadyExistsError, EDDDetailNotFoundError
from schemas import (
    EnhancedKYCCaseRead, EnhancedKYCCaseCreate, EnhancedKYCCaseUpdate, 
    EnhancedKYCCaseList, EDDDetailRead, EDDDetailCreate, EDDDetailUpdate,
    CaseStatusUpdate
)
from models import CaseStatus
from main import KYCServiceException # Import custom exception to use its to_http_exception method

# Production implementation for a simple authentication dependency
def get_current_user(token: str = Query(..., description="Bearer token for authentication")) -> Dict[str, Any]:
    # In a real application, this would validate the token and return a user object
    # For this task, we'll just check for a non-empty token
    if not token:
        raise KYCServiceException(
            name="AuthenticationError",
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or invalid."
        )
    # Return a dummy user ID for demonstration
    return {"user_id": "auth_user_123", "is_admin": True}

router = APIRouter()

# Dependency to get the service instance
def get_kyc_service(db: Session = Depends(get_db)) -> None:
    return KYCService(db)

# --- EnhancedKYCCase Endpoints (CRUD) ---

@router.post(
    "/cases", 
    response_model=EnhancedKYCCaseRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Enhanced KYC Case",
    description="Initiates a new Enhanced Due Diligence (EDD) case for a high-risk customer."
)
def create_kyc_case(
    case_data: EnhancedKYCCaseCreate, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Create a new Enhanced KYC Case.
    Raises: 409 Conflict if an active case already exists for the customer.
    """
    try:
        return kyc_service.create_case(case_data)
    except CaseAlreadyExistsError as e:
        raise e.to_http_exception()

@router.get(
    "/cases", 
    response_model=EnhancedKYCCaseList,
    summary="List all Enhanced KYC Cases",
    description="Retrieves a paginated list of all EDD cases, with optional filtering by status."
)
def list_kyc_cases(
    skip: int = Query(0, ge=0), 
    limit: int = Query(100, le=1000),
    status_filter: Optional[CaseStatus] = Query(None, description="Filter cases by status"),
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    List all Enhanced KYC Cases with pagination and optional status filter.
    """
    cases = kyc_service.get_cases(skip=skip, limit=limit, status_filter=status_filter)
    total = kyc_service.get_case_count(status_filter=status_filter)
    return EnhancedKYCCaseList(cases=cases, total=total)

@router.get(
    "/cases/{case_id}", 
    response_model=EnhancedKYCCaseRead,
    summary="Get a specific Enhanced KYC Case",
    description="Retrieves the details of a single EDD case by its ID."
)
def get_kyc_case(
    case_id: int, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Get a specific Enhanced KYC Case by ID.
    Raises: 404 Not Found if the case does not exist.
    """
    try:
        return kyc_service.get_case(case_id)
    except CaseNotFoundError as e:
        raise e.to_http_exception()

@router.patch(
    "/cases/{case_id}", 
    response_model=EnhancedKYCCaseRead,
    summary="Update an Enhanced KYC Case",
    description="Updates the metadata (e.g., risk level, analyst assignment) of an existing EDD case."
)
def update_kyc_case(
    case_id: int, 
    case_data: EnhancedKYCCaseUpdate, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Update an Enhanced KYC Case by ID.
    Raises: 404 Not Found if the case does not exist.
    """
    try:
        return kyc_service.update_case(case_id, case_data)
    except CaseNotFoundError as e:
        raise e.to_http_exception()

@router.delete(
    "/cases/{case_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Enhanced KYC Case",
    description="Deletes an EDD case and all associated details. (Requires Admin/Superuser role)"
)
def delete_kyc_case(
    case_id: int, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Delete an Enhanced KYC Case by ID.
    Raises: 404 Not Found if the case does not exist.
    """
    # Simple authorization check
    if not auth_user.get("is_admin"):
        raise KYCServiceException(
            name="AuthorizationError",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete cases."
        )
        
    try:
        kyc_service.delete_case(case_id)
        return
    except CaseNotFoundError as e:
        raise e.to_http_exception()

# --- EDDDetail Endpoints (CRUD for Sub-Resource) ---

@router.post(
    "/cases/{case_id}/details", 
    response_model=EDDDetailRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create EDD Details for a Case",
    description="Adds the detailed findings of the EDD process to a specific case."
)
def create_edd_detail(
    case_id: int, 
    detail_data: EDDDetailCreate, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Create EDD Details for a specific case.
    Raises: 404 Not Found if the case does not exist.
    """
    try:
        return kyc_service.create_edd_detail(case_id, detail_data)
    except CaseNotFoundError as e:
        raise e.to_http_exception()

@router.get(
    "/cases/{case_id}/details", 
    response_model=EDDDetailRead,
    summary="Get EDD Details for a Case",
    description="Retrieves the detailed findings associated with a specific EDD case."
)
def get_edd_detail(
    case_id: int, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Get EDD Details for a specific case.
    Raises: 404 Not Found if the case or details do not exist.
    """
    try:
        return kyc_service.get_edd_detail(case_id)
    except (CaseNotFoundError, EDDDetailNotFoundError) as e:
        raise e.to_http_exception()

@router.patch(
    "/cases/{case_id}/details", 
    response_model=EDDDetailRead,
    summary="Update EDD Details for a Case",
    description="Updates the detailed findings of the EDD process for a specific case."
)
def update_edd_detail(
    case_id: int, 
    detail_data: EDDDetailUpdate, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Update EDD Details for a specific case.
    Raises: 404 Not Found if the case or details do not exist.
    """
    try:
        return kyc_service.update_edd_detail(case_id, detail_data)
    except (CaseNotFoundError, EDDDetailNotFoundError) as e:
        raise e.to_http_exception()

@router.delete(
    "/cases/{case_id}/details", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete EDD Details for a Case",
    description="Deletes the detailed findings associated with a specific EDD case. (Requires Admin/Superuser role)"
)
def delete_edd_detail(
    case_id: int, 
    kyc_service: KYCService = Depends(get_kyc_service),
    auth_user: dict = Depends(get_current_user) # Security
) -> None:
    """
    Delete EDD Details for a specific case.
    Raises: 404 Not Found if the case or details do not exist.
    """
    # Simple authorization check
    if not auth_user.get("is_admin"):
        raise KYCServiceException(
            name="AuthorizationError",
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete EDD details."
        )
        
    try:
        kyc_service.delete_edd_detail(case_id)
        return
    except (CaseNotFoundError, EDDDetailNotFoundError) as e:
        raise e.to_http_exception()