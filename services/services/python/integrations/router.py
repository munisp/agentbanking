from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas import (
    Integration, IntegrationCreate, IntegrationUpdate, Message,
    IntegrationLog, IntegrationLogCreate
)
from service import (
    IntegrationService, IntegrationNotFoundError, IntegrationAlreadyExistsError,
    IntegrationServiceError
)
from config import logger

# --- Router Initialization ---

router = APIRouter(
    prefix="/integrations",
    tags=["Integrations"],
)

# --- Dependency Injection for Service Layer ---

def get_integration_service(db: Session = Depends(get_db)) -> IntegrationService:
    """Provides the IntegrationService instance with a database session."""
    return IntegrationService(db)

# --- Exception Handling Helper ---

def handle_service_errors(func) -> None:
    """Decorator to handle common service layer exceptions and convert them to HTTPExceptions."""
    async def wrapper(*args, **kwargs) -> None:
        try:
            # Check if the function is async and call it correctly
            if hasattr(func, '__code__') and 'async' in func.__code__.co_names:
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except IntegrationNotFoundError as e:
            logger.warning(f"Resource not found: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except IntegrationAlreadyExistsError as e:
            logger.warning(f"Resource conflict: {e}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        except IntegrationServiceError as e:
            logger.error(f"Internal service error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred in the service layer."
            )
    return wrapper

# --- Integration Endpoints ---

@router.post(
    "/", 
    response_model=Integration, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Integration"
)
@handle_service_errors
def create_integration(
    integration_data: IntegrationCreate,
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Registers a new third-party integration in the system.
    The API key provided will be securely stored (simulated encryption).
    """
    return service.create_integration(integration_data)

@router.get(
    "/", 
    response_model=List[Integration],
    summary="List all Integrations"
)
@handle_service_errors
def list_integrations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Retrieves a list of all registered integrations with pagination.
    """
    return service.list_integrations(skip=skip, limit=limit)

@router.get(
    "/{integration_id}", 
    response_model=Integration,
    summary="Get Integration by ID"
)
@handle_service_errors
def get_integration(
    integration_id: UUID,
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Retrieves a single integration by its unique ID.
    """
    return service.get_integration_by_id(integration_id)

@router.put(
    "/{integration_id}", 
    response_model=Integration,
    summary="Update an existing Integration"
)
@handle_service_errors
def update_integration(
    integration_id: UUID,
    integration_data: IntegrationUpdate,
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Updates the details of an existing integration. 
    Only fields provided in the request body will be updated.
    """
    return service.update_integration(integration_id, integration_data)

@router.delete(
    "/{integration_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Integration"
)
@handle_service_errors
def delete_integration(
    integration_id: UUID,
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Deletes an integration and all its associated logs.
    """
    service.delete_integration(integration_id)
    return

# --- Integration Log Endpoints ---

@router.post(
    "/{integration_id}/logs",
    response_model=IntegrationLog,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Integration Log entry"
)
@handle_service_errors
def create_log_entry(
    integration_id: UUID,
    log_data: IntegrationLogCreate,
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Creates a log entry for a specific integration's API call.
    This is typically used by the application to record external API interactions.
    """
    # Ensure the log data contains the correct integration_id
    if log_data.integration_id != integration_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration ID in path and body must match."
        )
    return service.create_integration_log(log_data)

@router.get(
    "/{integration_id}/logs",
    response_model=List[IntegrationLog],
    summary="List logs for a specific Integration"
)
@handle_service_errors
def list_integration_logs(
    integration_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    service: IntegrationService = Depends(get_integration_service)
) -> None:
    """
    Retrieves a paginated list of all API call logs for a given integration.
    """
    return service.list_integration_logs(integration_id, skip=skip, limit=limit)
