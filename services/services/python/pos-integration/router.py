import logging
import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db
from .models import (
    POSIntegration,
    POSIntegrationActivityLog,
    POSIntegrationCreate,
    POSIntegrationResponse,
    POSIntegrationUpdate,
    POSIntegrationDetailResponse,
    POSIntegrationActivityLogResponse,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations",
    tags=["pos-integration"],
    responses={404: {"description": "Not found"}},
)


# --- Helper Functions ---

def get_integration_or_404(db: Session, integration_id: UUID) -> POSIntegration:
    """
    Fetches a POSIntegration by ID or raises a 404 HTTPException.
    """
    integration = db.query(POSIntegration).filter(POSIntegration.id == integration_id).first()
    if not integration:
        logger.warning(f"POSIntegration with ID {integration_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POSIntegration with ID {integration_id} not found.",
        )
    return integration


# --- CRUD Endpoints for POSIntegration ---

@router.post(
    "/",
    response_model=POSIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new POS Integration",
    description="Registers a new Point-of-Sale system integration configuration.",
)
def create_integration(
    integration_in: POSIntegrationCreate, db: Session = Depends(get_db)
):
    """
    Creates a new POS Integration record in the database.
    
    Args:
        integration_in: The data for the new integration.
        db: The database session dependency.
        
    Returns:
        The created POSIntegration object.
        
    Raises:
        HTTPException 409: If an integration with the same name already exists.
    """
    logger.info(f"Attempting to create new POSIntegration: {integration_in.name}")
    db_integration = POSIntegration(**integration_in.dict())
    
    try:
        db.add(db_integration)
        db.commit()
        db.refresh(db_integration)
        logger.info(f"Successfully created POSIntegration with ID: {db_integration.id}")
        return db_integration
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error when creating POSIntegration: {integration_in.name}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"POSIntegration with name '{integration_in.name}' already exists.",
        )


@router.get(
    "/",
    response_model=List[POSIntegrationResponse],
    summary="List all POS Integrations",
    description="Retrieves a list of all configured Point-of-Sale system integrations.",
)
def list_integrations(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieves a list of POS Integration records.
    
    Args:
        skip: The number of records to skip (for pagination).
        limit: The maximum number of records to return.
        db: The database session dependency.
        
    Returns:
        A list of POSIntegration objects.
    """
    integrations = db.query(POSIntegration).offset(skip).limit(limit).all()
    return integrations


@router.get(
    "/{integration_id}",
    response_model=POSIntegrationDetailResponse,
    summary="Get a specific POS Integration",
    description="Retrieves a single POS Integration configuration by its unique ID, including recent activity logs.",
)
def get_integration(integration_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single POS Integration record by ID.
    
    Args:
        integration_id: The unique ID of the integration.
        db: The database session dependency.
        
    Returns:
        The POSIntegration object with its recent activity logs.
        
    Raises:
        HTTPException 404: If the integration is not found.
    """
    # Fetch the integration
    integration = get_integration_or_404(db, integration_id)
    
    # Fetch and limit activity logs for the detail view
    activity_logs = (
        db.query(POSIntegrationActivityLog)
        .filter(POSIntegrationActivityLog.integration_id == integration_id)
        .order_by(POSIntegrationActivityLog.timestamp.desc())
        .limit(10) # Limit to 10 recent logs
        .all()
    )
    
    # Attach logs to the integration object for the Pydantic response model
    # Note: This relies on the ORM object being able to accept the 'activity_logs' attribute
    # which is defined as a relationship in the model.
    integration.activity_logs = activity_logs
    
    return integration


@router.put(
    "/{integration_id}",
    response_model=POSIntegrationResponse,
    summary="Update a POS Integration",
    description="Updates an existing Point-of-Sale system integration configuration.",
)
def update_integration(
    integration_id: UUID,
    integration_in: POSIntegrationUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing POS Integration record.
    
    Args:
        integration_id: The unique ID of the integration to update.
        integration_in: The update data.
        db: The database session dependency.
        
    Returns:
        The updated POSIntegration object.
        
    Raises:
        HTTPException 404: If the integration is not found.
        HTTPException 409: If the update causes a name conflict.
    """
    db_integration = get_integration_or_404(db, integration_id)

    update_data = integration_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_integration, key, value)

    try:
        db.add(db_integration)
        db.commit()
        db.refresh(db_integration)
        logger.info(f"Successfully updated POSIntegration with ID: {integration_id}")
        return db_integration
    except IntegrityError:
        db.rollback()
        logger.error(f"Integrity error when updating POSIntegration ID: {integration_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A POSIntegration with the same name already exists.",
        )


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a POS Integration",
    description="Deletes a Point-of-Sale system integration configuration by its unique ID.",
)
def delete_integration(integration_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes a POS Integration record.
    
    Args:
        integration_id: The unique ID of the integration to delete.
        db: The database session dependency.
        
    Raises:
        HTTPException 404: If the integration is not found.
    """
    db_integration = get_integration_or_404(db, integration_id)

    db.delete(db_integration)
    db.commit()
    logger.info(f"Successfully deleted POSIntegration with ID: {integration_id}")
    return {"ok": True}


# --- Business Logic Endpoints ---

@router.post(
    "/{integration_id}/sync",
    response_model=POSIntegrationActivityLogResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual synchronization",
    description="Triggers a manual data synchronization for the specified POS Integration. Returns a log entry for the triggered event.",
)
def trigger_sync(integration_id: UUID, db: Session = Depends(get_db)):
    """
    Triggers a manual sync process for the POS integration.
    
    Args:
        integration_id: The unique ID of the integration to sync.
        db: The database session dependency.
        
    Returns:
        The created POSIntegrationActivityLog object for the sync trigger.
        
    Raises:
        HTTPException 404: If the integration is not found.
    """
    db_integration = get_integration_or_404(db, integration_id)
    
    logger.info(f"Triggering manual sync for integration: {db_integration.name} ({integration_id})")
    
    # In a real application, this would dispatch an asynchronous task.
    # Here, we only log the event and update the last_sync_at time.
    
    # 1. Create an activity log entry for the sync start
    sync_log = POSIntegrationActivityLog(
        integration_id=integration_id,
        activity_type="MANUAL_SYNC_TRIGGERED",
        details=f"Manual sync triggered by API for integration type: {db_integration.integration_type}",
        timestamp=datetime.datetime.utcnow()
    )
    
    db.add(sync_log)
    
    # 2. Update the last_sync_at time on the integration
    db_integration.last_sync_at = datetime.datetime.utcnow()
    db.add(db_integration)
    
    db.commit()
    db.refresh(sync_log)
    
    return sync_log
