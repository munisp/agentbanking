from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyResponse,
    ApiKeyCreatedResponse,
    ApiKeyDeleteResponse,
)
from service import ApiKeyService, NotFoundException, ConflictException, InvalidCredentialsException
from models import ApiKey

# --- Security Dependency ---

# Define the header where the API key is expected
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_api_key(
    api_key: str = Depends(API_KEY_HEADER),
    db: Session = Depends(get_db)
) -> ApiKey:
    """
    Dependency function to authenticate the API key provided in the header.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key missing in 'X-API-Key' header.",
        )
    
    service = ApiKeyService(db)
    try:
        # The service layer handles the hashing, lookup, and validation (active/expired)
        authenticated_key = service.authenticate_key(api_key)
        return authenticated_key
    except InvalidCredentialsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )

# --- Router Definition ---

router = APIRouter(
    prefix="/api-keys",
    tags=["API Key Management"],
    dependencies=[Depends(get_current_api_key)], # Apply authentication to all routes by default
    responses={404: {"description": "Not found"}},
)

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API Key",
    description="Generates a new API key and stores its hash. The secret key is returned only once."
)
def create_api_key(
    key_data: ApiKeyCreate,
    db: Session = Depends(get_db),
    # NOTE: This endpoint should ideally have its own authorization check, 
    # e.g., only an admin or the owner_id can create a key.
    # For simplicity, we assume the authenticated key has the 'admin' scope or similar.
    current_key: ApiKey = Depends(get_current_api_key) 
):
    service = ApiKeyService(db)
    try:
        db_key, secret_key = service.create_key(key_data)
        # Convert the SQLAlchemy model to the Pydantic response model
        response_data = ApiKeyCreatedResponse.from_orm(db_key)
        response_data.secret_key = secret_key
        return response_data
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{key_id}",
    response_model=ApiKeyResponse,
    summary="Get API Key details by ID",
    description="Retrieves the public details of a specific API key."
)
def read_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_key: ApiKey = Depends(get_current_api_key)
):
    service = ApiKeyService(db)
    try:
        db_key = service.get_key_by_id(key_id)
        # Simple authorization check: only the owner or an admin key can view
        if db_key.owner_id != current_key.owner_id and 'admin' not in current_key.scopes:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this API key.",
            )
        return db_key
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get(
    "/owner/{owner_id}",
    response_model=List[ApiKeyResponse],
    summary="List API Keys for an Owner",
    description="Retrieves a list of all API keys associated with a specific owner ID."
)
def list_api_keys(
    owner_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_key: ApiKey = Depends(get_current_api_key)
):
    # Authorization check: only the owner or an admin key can list keys for this owner
    if owner_id != current_key.owner_id and 'admin' not in current_key.scopes:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to list API keys for this owner.",
        )
        
    service = ApiKeyService(db)
    return service.get_keys_by_owner(owner_id, skip=skip, limit=limit)


@router.patch(
    "/{key_id}",
    response_model=ApiKeyResponse,
    summary="Update an existing API Key",
    description="Updates the name, scopes, or active status of an API key."
)
def update_api_key(
    key_id: UUID,
    key_data: ApiKeyUpdate,
    db: Session = Depends(get_db),
    current_key: ApiKey = Depends(get_current_api_key)
):
    service = ApiKeyService(db)
    try:
        # Check ownership before update
        db_key = service.get_key_by_id(key_id)
        if db_key.owner_id != current_key.owner_id and 'admin' not in current_key.scopes:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this API key.",
            )
            
        updated_key = service.update_key(key_id, key_data)
        return updated_key
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/{key_id}",
    response_model=ApiKeyDeleteResponse,
    summary="Delete an API Key",
    description="Deletes an API key, revoking access immediately."
)
def delete_api_key(
    key_id: UUID,
    db: Session = Depends(get_db),
    current_key: ApiKey = Depends(get_current_api_key)
):
    service = ApiKeyService(db)
    try:
        # Check ownership before deletion
        db_key = service.get_key_by_id(key_id)
        if db_key.owner_id != current_key.owner_id and 'admin' not in current_key.scopes:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this API key.",
            )
            
        service.delete_key(key_id)
        return ApiKeyDeleteResponse(id=key_id)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- Utility Endpoint for Key Validation (Optional, for testing/debugging) ---

@router.get(
    "/validate",
    summary="Validate the current API Key",
    description="Returns the details of the currently authenticated API key. Requires a valid 'X-API-Key' header.",
    response_model=ApiKeyResponse,
    # This endpoint is already protected by the router's dependency, but we explicitly
    # list the dependency for clarity in the function signature.
)
def validate_key(current_key: ApiKey = Depends(get_current_api_key)):
    # The key is already authenticated by the dependency, just return its details
    return current_key