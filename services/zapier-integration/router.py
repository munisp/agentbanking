import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Assuming config.py and models.py are in the same directory
from config import get_db
from models import (
    Base,
    ZapierIntegration,
    ZapierIntegrationCreate,
    ZapierIntegrationUpdate,
    ZapierIntegrationResponse,
    ZapierIntegrationDetailResponse,
    ZapierIntegrationLog,
    ZapierIntegrationLogCreate,
    ZapierIntegrationLogResponse,
)

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Define the router
router = APIRouter(
    prefix="/integrations",
    tags=["zapier-integration"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (Service Layer Simulation) ---

def get_integration_by_id(db: Session, integration_id: uuid.UUID) -> ZapierIntegration:
    """Fetches a ZapierIntegration by its ID, raising 404 if not found."""
    integration = db.query(ZapierIntegration).filter(ZapierIntegration.id == integration_id).first()
    if not integration:
        logger.warning(f"Integration not found: {integration_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zapier Integration with ID {integration_id} not found",
        )
    return integration

# --- CRUD Endpoints for ZapierIntegration ---

@router.post(
    "/",
    response_model=ZapierIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Zapier Integration",
    description="Registers a new Zapier integration for a specific user.",
)
def create_integration(
    integration_data: ZapierIntegrationCreate, db: Session = Depends(get_db)
):
    """
    Creates a new Zapier Integration record in the database.

    Args:
        integration_data: The data for the new integration.
        db: The database session dependency.

    Returns:
        The created ZapierIntegration object.
    """
    # Check for existing integration with the same user_id and name
    existing_integration = db.query(ZapierIntegration).filter(
        ZapierIntegration.user_id == integration_data.user_id,
        ZapierIntegration.name == integration_data.name
    ).first()

    if existing_integration:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration with name '{integration_data.name}' already exists for user {integration_data.user_id}",
        )

    db_integration = ZapierIntegration(**integration_data.model_dump())
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    logger.info(f"Created new integration: {db_integration.id}")
    return db_integration


@router.get(
    "/{integration_id}",
    response_model=ZapierIntegrationDetailResponse,
    summary="Get a Zapier Integration by ID",
    description="Retrieves a specific Zapier integration, including its recent activity logs.",
)
def read_integration(
    integration_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    Retrieves a single Zapier Integration by its unique ID.

    Args:
        integration_id: The unique ID of the integration.
        db: The database session dependency.

    Returns:
        The ZapierIntegration object with logs.
    """
    integration = get_integration_by_id(db, integration_id)
    return integration


@router.get(
    "/",
    response_model=List[ZapierIntegrationResponse],
    summary="List all Zapier Integrations",
    description="Retrieves a list of all configured Zapier integrations.",
)
def list_integrations(
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Retrieves a list of Zapier Integrations, optionally filtered by user ID.

    Args:
        user_id: Optional user ID to filter integrations.
        skip: Number of records to skip for pagination.
        limit: Maximum number of records to return.
        db: The database session dependency.

    Returns:
        A list of ZapierIntegration objects.
    """
    query = db.query(ZapierIntegration)
    if user_id is not None:
        query = query.filter(ZapierIntegration.user_id == user_id)

    integrations = query.offset(skip).limit(limit).all()
    return integrations


@router.put(
    "/{integration_id}",
    response_model=ZapierIntegrationResponse,
    summary="Update a Zapier Integration",
    description="Updates the details of an existing Zapier integration.",
)
def update_integration(
    integration_id: uuid.UUID,
    integration_data: ZapierIntegrationUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing Zapier Integration record.

    Args:
        integration_id: The unique ID of the integration to update.
        integration_data: The data to update the integration with.
        db: The database session dependency.

    Returns:
        The updated ZapierIntegration object.
    """
    db_integration = get_integration_by_id(db, integration_id)

    update_data = integration_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_integration, key, value)

    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    logger.info(f"Updated integration: {db_integration.id}")
    return db_integration


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Zapier Integration",
    description="Deletes a Zapier integration and all associated logs.",
)
def delete_integration(
    integration_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    Deletes a Zapier Integration record.

    Args:
        integration_id: The unique ID of the integration to delete.
        db: The database session dependency.
    """
    db_integration = get_integration_by_id(db, integration_id)

    db.delete(db_integration)
    db.commit()
    logger.info(f"Deleted integration: {integration_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.post(
    "/{integration_id}/log",
    response_model=ZapierIntegrationLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log activity for an Integration",
    description="Records an activity log entry for a specific Zapier integration.",
)
def log_integration_activity(
    integration_id: uuid.UUID,
    log_data: ZapierIntegrationLogCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a new log entry associated with a Zapier Integration.

    Args:
        integration_id: The unique ID of the integration to log against.
        log_data: The data for the new log entry.
        db: The database session dependency.

    Returns:
        The created ZapierIntegrationLog object.
    """
    # Ensure the integration exists
    get_integration_by_id(db, integration_id)

    # Create the log entry
    db_log = ZapierIntegrationLog(
        integration_id=integration_id,
        level=log_data.level,
        message=log_data.message,
        payload=log_data.payload,
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Logged activity for integration {integration_id}: {db_log.level}")
    return db_log

@router.post(
    "/{integration_id}/test",
    summary="Test Zapier Connection",
    description="Triggers a test of the connection to the Zapier endpoint.",
)
def test_integration_connection(
    integration_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    Triggers testing the connection for a Zapier Integration.
    In a real application, this would involve an external API call.

    Args:
        integration_id: The unique ID of the integration to test.
        db: The database session dependency.

    Returns:
        A status message indicating the result of the test.
    """
    db_integration = get_integration_by_id(db, integration_id)

    # Test connection to Zapier webhook
    if db_integration.is_active:
        test_status = "success"
        message = f"Connection test for '{db_integration.name}' successful. API Key length: {len(db_integration.api_key)}"
        log_level = "INFO"
    else:
        test_status = "failure"
        message = f"Connection test for '{db_integration.name}' failed: Integration is inactive."
        log_level = "WARNING"

    # Log the test result
    db_log = ZapierIntegrationLog(
        integration_id=integration_id,
        level=log_level,
        message=f"Connection Test: {message}",
        payload=f'{{"status": "{test_status}"}}',
    )
    db.add(db_log)
    db.commit()

    return {"status": test_status, "message": message}
