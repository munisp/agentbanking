from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Security
from sqlalchemy.orm import Session
from . import schemas, service, database, models
from fastapi.security import APIKeyHeader
import json

# --- Router Setup ---
router = APIRouter(
    prefix="/api/v1",
    tags=["verification"],
)

# --- Security Dependency ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_current_partner(
    api_key: str = Security(api_key_header),
    db: Session = Depends(database.get_db)
) -> models.Partner:
    """Authenticates the partner using the API key."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=schemas.APIExceptionSchema(
                detail="Missing API Key",
                code="MISSING_API_KEY"
            ).model_dump()
        )
    try:
        partner = service.get_partner_by_api_key(db, api_key)
        return partner
    except service.UnauthorizedException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=schemas.APIExceptionSchema(
                detail=e.detail,
                code=e.code
            ).model_dump()
        )

# --- Verification Request Endpoints ---

@router.post(
    "/requests",
    response_model=schemas.VerificationRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new verification request (KYC or KYB)",
    description="Submits a new identity verification request to the white-label engine."
)
def create_request(
    request_data: schemas.VerificationRequestCreate,
    partner: models.Partner = Depends(get_current_partner),
    db: Session = Depends(database.get_db)
):
    try:
        db_request = service.create_verification_request(
            db=db,
            partner_id=partner.id,
            request_data=request_data
        )
        # Convert subject_data and result_details from string/text to dict for Pydantic validation
        db_request.subject_data = json.loads(db_request.subject_data)
        if db_request.result_details:
            db_request.result_details = json.loads(db_request.result_details)
            
        return db_request
    except service.ConflictException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=schemas.APIExceptionSchema(
                detail=e.detail,
                code=e.code
            ).model_dump()
        )

@router.get(
    "/requests/{request_id}",
    response_model=schemas.VerificationRequestResponse,
    summary="Retrieve a specific verification request",
    description="Fetches the details and current status of a verification request by its ID."
)
def read_request(
    request_id: int,
    partner: models.Partner = Depends(get_current_partner),
    db: Session = Depends(database.get_db)
):
    try:
        db_request = service.get_verification_request(
            db=db,
            request_id=request_id,
            partner_id=partner.id
        )
        # Convert subject_data and result_details from string/text to dict
        db_request.subject_data = json.loads(db_request.subject_data)
        if db_request.result_details:
            db_request.result_details = json.loads(db_request.result_details)
            
        return db_request
    except service.NotFoundException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=schemas.APIExceptionSchema(
                detail=e.detail,
                code=e.code
            ).model_dump()
        )

@router.get(
    "/requests",
    response_model=schemas.VerificationRequestListResponse,
    summary="List all verification requests",
    description="Returns a paginated list of all verification requests submitted by the authenticated partner."
)
def list_requests(
    skip: int = 0,
    limit: int = 100,
    partner: models.Partner = Depends(get_current_partner),
    db: Session = Depends(database.get_db)
):
    requests = service.list_verification_requests(
        db=db,
        partner_id=partner.id,
        skip=skip,
        limit=limit
    )
    total = service.count_verification_requests(db=db, partner_id=partner.id)
    
    # Convert subject_data and result_details from string/text to dict for all requests
    for req in requests:
        req.subject_data = json.loads(req.subject_data)
        if req.result_details:
            req.result_details = json.loads(req.result_details)
            
    return schemas.VerificationRequestListResponse(total=total, requests=requests)

@router.put(
    "/requests/{request_id}",
    response_model=schemas.VerificationRequestResponse,
    summary="Update a verification request (Internal/Webhook Use)",
    description="Updates the status and result details of a verification request. This is typically used by internal systems or webhooks."
)
def update_request(
    request_id: int,
    update_data: schemas.VerificationRequestUpdate,
    partner: models.Partner = Depends(get_current_partner),
    db: Session = Depends(database.get_db)
):
    try:
        db_request = service.update_verification_request(
            db=db,
            request_id=request_id,
            partner_id=partner.id,
            update_data=update_data
        )
        # Convert subject_data and result_details from string/text to dict
        db_request.subject_data = json.loads(db_request.subject_data)
        if db_request.result_details:
            db_request.result_details = json.loads(db_request.result_details)
            
        return db_request
    except service.NotFoundException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=schemas.APIExceptionSchema(
                detail=e.detail,
                code=e.code
            ).model_dump()
        )

@router.delete(
    "/requests/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a verification request",
    description="Deletes a verification request by its ID."
)
def delete_request(
    request_id: int,
    partner: models.Partner = Depends(get_current_partner),
    db: Session = Depends(database.get_db)
):
    try:
        service.delete_verification_request(
            db=db,
            request_id=request_id,
            partner_id=partner.id
        )
        return
    except service.NotFoundException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=schemas.APIExceptionSchema(
                detail=e.detail,
                code=e.code
            ).model_dump()
        )

# --- Partner Management Endpoints (Admin/Internal Use) ---

@router.post(
    "/admin/partners",
    response_model=schemas.PartnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new partner (Admin Only)",
    description="Creates a new partner account and returns the generated API key. **This key is only shown once.**"
)
def create_partner_endpoint(
    partner_data: schemas.PartnerCreate,
    db: Session = Depends(database.get_db)
):
    # NOTE: In a real system, this endpoint would be protected by a separate Admin API Key or OAuth flow.
    # For this exercise, we assume the caller has admin privileges.
    try:
        return service.create_partner(db=db, partner_data=partner_data)
    except service.ConflictException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=schemas.APIExceptionSchema(
                detail=e.detail,
                code=e.code
            ).model_dump()
        )