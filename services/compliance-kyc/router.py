from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from database import get_db
from service import KYCService, get_kyc_service
from schemas import (
    KYCRecordInDB, KYCRecordCreate, KYCRecordUpdate, KYCRecordList,
    KYCDocumentInDB, KYCDocumentCreate, KYCDocumentUpdate,
    KYCCheckInDB, KYCCheckCreate, KYCCheckUpdate,
    Message
)
from config import settings

# Define the router
kyc_router = APIRouter()

# --- JWT Authentication Dependency ---
# The previous mock_auth dependency always returned True (even its
# "disabled" branch was a no-op pass), giving unauthenticated access to all
# KYC records. Authentication is now a real JWT check on every endpoint.
_bearer_scheme = HTTPBearer(auto_error=True)

async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)
) -> dict:
    """Validate the Bearer JWT. Fails closed: 401 on any invalid token and
    503 if the JWT library is unavailable."""
    token = credentials.credentials
    try:
        import jwt  # PyJWT
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT validation is unavailable on this service"
        )
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return payload

# --- KYC Record Endpoints ---

@kyc_router.post(
    "/records", 
    response_model=KYCRecordInDB, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new KYC Record"
)
async def create_kyc_record(
    record_in: KYCRecordCreate,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Creates a new KYC record for a customer.
    The `customer_id` must be unique.
    """
    return await kyc_service.create_record(record_in)

@kyc_router.get(
    "/records", 
    response_model=KYCRecordList, 
    summary="List all KYC Records"
)
async def list_kyc_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Retrieves a list of all KYC records with pagination.
    """
    records = await kyc_service.list_records(skip=skip, limit=limit)
    # For a proper list response, we should also get the total count
    # For simplicity in this example, we'll return the list directly and wrap it in the schema
    # A more complete implementation would involve a separate count query.
    return KYCRecordList(total=len(records), records=records)

@kyc_router.get(
    "/records/{record_id}", 
    response_model=KYCRecordInDB, 
    summary="Get a KYC Record by ID"
)
async def get_kyc_record(
    record_id: int,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Retrieves a single KYC record by its internal ID, including all associated documents and checks.
    """
    return await kyc_service.get_record(record_id)

@kyc_router.put(
    "/records/{record_id}", 
    response_model=KYCRecordInDB, 
    summary="Update a KYC Record"
)
async def update_kyc_record(
    record_id: int,
    record_in: KYCRecordUpdate,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Updates the status, risk score, reviewer, or rejection reason of an existing KYC record.
    """
    return await kyc_service.update_record(record_id, record_in)

@kyc_router.delete(
    "/records/{record_id}", 
    status_code=status.HTTP_204_NO_CONTENT, 
    response_model=None,
    summary="Delete a KYC Record"
)
async def delete_kyc_record(
    record_id: int,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Deletes a KYC record and all associated documents and checks.
    """
    await kyc_service.delete_record(record_id)
    return None # 204 No Content response

# --- Document Endpoints ---

@kyc_router.post(
    "/records/{record_id}/documents", 
    response_model=KYCDocumentInDB, 
    status_code=status.HTTP_201_CREATED,
    summary="Add a Document to a KYC Record"
)
async def add_document_to_record(
    record_id: int,
    document_in: KYCDocumentCreate,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Adds a new document (e.g., passport, ID) to an existing KYC record.
    """
    return await kyc_service.add_document(record_id, document_in)

@kyc_router.patch(
    "/documents/{document_id}", 
    response_model=KYCDocumentInDB, 
    summary="Update Document Verification Status"
)
async def update_document_status(
    document_id: int,
    document_in: KYCDocumentUpdate,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Manually updates the verification status of a specific document.
    """
    return await kyc_service.update_document_status(document_id, document_in)

# --- Check Endpoints ---

@kyc_router.post(
    "/records/{record_id}/checks", 
    response_model=KYCCheckInDB, 
    status_code=status.HTTP_201_CREATED,
    summary="Add a Compliance Check to a KYC Record"
)
async def add_check_to_record(
    record_id: int,
    check_in: KYCCheckCreate,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Adds a new compliance check (e.g., PEP, Sanctions) to an existing KYC record.
    """
    return await kyc_service.add_check(record_id, check_in)

@kyc_router.patch(
    "/checks/{check_id}", 
    response_model=KYCCheckInDB, 
    summary="Update Compliance Check Status"
)
async def update_check_status(
    check_id: int,
    check_in: KYCCheckUpdate,
    kyc_service: KYCService = Depends(get_kyc_service),
    auth: dict = Depends(require_auth)
) -> None:
    """
    Updates the status and details of a specific compliance check.
    """
    return await kyc_service.update_check_status(check_id, check_in)
