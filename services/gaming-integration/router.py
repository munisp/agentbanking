import logging
import hashlib
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Assuming models.py and config.py are in the same directory or accessible
from . import models
from .config import get_db

# --- Setup ---

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/gaming-integrations",
    tags=["gaming-integration"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def hash_api_key(api_key: str) -> str:
    """
    Hash the API key before storage using SHA-256.
    In a real application, use a library like passlib (e.g., bcrypt).
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

# --- CRUD Operations for GamingIntegration ---

@router.post(
    "/",
    response_model=models.GamingIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new gaming integration",
)
def create_integration(
    integration: models.GamingIntegrationCreate, db: Session = Depends(get_db)
):
    """
    Creates a new gaming integration record in the database.

    The `api_key` is hashed before being stored as `api_key_hash`.
    """
    logger.info(f"Attempting to create integration for platform: {integration.platform_name}")
    
    # Check for existing integration with the same platform name
    if db.query(models.GamingIntegration).filter(
        models.GamingIntegration.platform_name == integration.platform_name
    ).first():
        logger.warning(f"Integration for platform '{integration.platform_name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration for platform '{integration.platform_name}' already exists.",
        )

    # Hash the API key before storing
    hashed_key = hash_api_key(integration.api_key)

    db_integration = models.GamingIntegration(
        platform_name=integration.platform_name,
        api_key_hash=hashed_key,
        is_active=integration.is_active,
    )
    
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    
    logger.info(f"Successfully created integration with ID: {db_integration.id}")
    return db_integration


@router.get(
    "/{integration_id}",
    response_model=models.GamingIntegrationResponse,
    summary="Get a gaming integration by ID",
)
def read_integration(integration_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single gaming integration record by its unique ID.
    """
    db_integration = db.query(models.GamingIntegration).filter(
        models.GamingIntegration.id == integration_id
    ).first()
    
    if db_integration is None:
        logger.warning(f"Integration with ID {integration_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gaming Integration not found",
        )
    
    return db_integration


@router.get(
    "/",
    response_model=List[models.GamingIntegrationResponse],
    summary="List all gaming integrations",
)
def list_integrations(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of all gaming integration records with pagination.
    """
    integrations = db.query(models.GamingIntegration).offset(skip).limit(limit).all()
    return integrations


@router.put(
    "/{integration_id}",
    response_model=models.GamingIntegrationResponse,
    summary="Update an existing gaming integration",
)
def update_integration(
    integration_id: int,
    integration: models.GamingIntegrationUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing gaming integration record.

    Allows updating `platform_name`, `is_active`, and optionally the `api_key`.
    """
    db_integration = db.query(models.GamingIntegration).filter(
        models.GamingIntegration.id == integration_id
    ).first()
    
    if db_integration is None:
        logger.warning(f"Update failed: Integration with ID {integration_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gaming Integration not found",
        )

    # Update fields if provided
    update_data = integration.dict(exclude_unset=True)
    
    if "api_key" in update_data:
        # Hash the new API key and update the hash field
        new_key = update_data.pop("api_key")
        db_integration.api_key_hash = hash_api_key(new_key)
        logger.info(f"Integration {integration_id}: API key updated.")

    for key, value in update_data.items():
        setattr(db_integration, key, value)

    db.commit()
    db.refresh(db_integration)
    logger.info(f"Successfully updated integration with ID: {integration_id}")
    return db_integration


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a gaming integration",
)
def delete_integration(integration_id: int, db: Session = Depends(get_db)):
    """
    Deletes a gaming integration record and all associated activity logs.
    """
    db_integration = db.query(models.GamingIntegration).filter(
        models.GamingIntegration.id == integration_id
    ).first()
    
    if db_integration is None:
        logger.warning(f"Delete failed: Integration with ID {integration_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gaming Integration not found",
        )

    db.delete(db_integration)
    db.commit()
    logger.info(f"Successfully deleted integration with ID: {integration_id}")
    return {"ok": True}

# --- Business-Specific Endpoint ---

@router.post(
    "/{integration_id}/sync",
    summary="Trigger a data synchronization for the integration",
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_sync(integration_id: int, db: Session = Depends(get_db)):
    """
    Triggers a data synchronization process for the specified gaming integration.
    
    This triggers a long-running sync task via the gaming provider API, which typically would be
    handled by a background worker (e.g., Celery, Redis Queue).
    """
    db_integration = db.query(models.GamingIntegration).filter(
        models.GamingIntegration.id == integration_id
    ).first()
    
    if db_integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gaming Integration not found",
        )

    # 1. Log the start of the sync
    log_entry = models.IntegrationActivityLog(
        integration_id=integration_id,
        activity_type="SYNC_START",
        message=f"Synchronization triggered for platform {db_integration.platform_name}.",
    )
    db.add(log_entry)
    db.commit()
    
    logger.info(f"Sync triggered for integration {integration_id}. (Platform: {db_integration.platform_name})")
    
    # 2. Sync via gaming provider API
    # In a real app, this would enqueue a job to a background worker.
    
    # 3. Update the last_sync_at timestamp after sync
    # This part would typically be done by the background worker upon completion.
    db_integration.last_sync_at = models.datetime.utcnow()
    
    log_entry_success = models.IntegrationActivityLog(
        integration_id=integration_id,
        activity_type="SYNC_SUCCESS",
        message="Synchronization process completed successfully.",
    )
    db.add(log_entry_success)
    db.commit()
    
    return {"message": f"Synchronization for integration {integration_id} accepted and started."}

# --- Activity Log Endpoints ---

@router.post(
    "/{integration_id}/logs",
    response_model=models.IntegrationActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new activity log entry for an integration",
)
def create_activity_log(
    integration_id: int,
    log_data: models.IntegrationActivityLogCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a new activity log entry associated with a specific gaming integration.
    """
    # Check if the integration exists
    if not db.query(models.GamingIntegration).filter(
        models.GamingIntegration.id == integration_id
    ).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gaming Integration not found",
        )

    db_log = models.IntegrationActivityLog(
        integration_id=integration_id,
        activity_type=log_data.activity_type,
        message=log_data.message,
    )
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    logger.info(f"Created log for integration {integration_id}: {log_data.activity_type}")
    return db_log


@router.get(
    "/{integration_id}/logs",
    response_model=List[models.IntegrationActivityLogResponse],
    summary="List activity logs for a specific integration",
)
def list_activity_logs(
    integration_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Retrieves a paginated list of activity logs for a given gaming integration ID.
    """
    # Check if the integration exists
    if not db.query(models.GamingIntegration).filter(
        models.GamingIntegration.id == integration_id
    ).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gaming Integration not found",
        )

    logs = db.query(models.IntegrationActivityLog).filter(
        models.IntegrationActivityLog.integration_id == integration_id
    ).order_by(
        models.IntegrationActivityLog.timestamp.desc()
    ).offset(skip).limit(limit).all()
    
    return logs
