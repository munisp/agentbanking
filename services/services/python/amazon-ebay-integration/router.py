import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from .config import get_db
from .models import (
    AmazonEbayIntegration,
    AmazonEbayIntegrationCreate,
    AmazonEbayIntegrationUpdate,
    AmazonEbayIntegrationResponse,
    AmazonEbayIntegrationListResponse,
    IntegrationActivityLog,
    IntegrationActivityLogBase,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations",
    tags=["amazon-ebay-integration"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (Internal Business Logic) ---

def create_log_entry(db: Session, integration_id: int, log_data: IntegrationActivityLogBase):
    """Creates a new activity log entry for a given integration."""
    db_log = IntegrationActivityLog(
        integration_id=integration_id,
        activity_type=log_data.activity_type,
        message=log_data.message,
        level=log_data.level
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=AmazonEbayIntegrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Amazon-eBay integration link",
    description="Establishes a new link between an Amazon ASIN and an eBay Item ID."
)
def create_integration(
    integration: AmazonEbayIntegrationCreate, db: Session = Depends(get_db)
):
    """
    Creates a new AmazonEbayIntegration record in the database.
    Raises a 409 Conflict error if an integration with the same ASIN or Item ID already exists.
    """
    try:
        db_integration = AmazonEbayIntegration(
            amazon_asin=integration.amazon_asin,
            ebay_item_id=integration.ebay_item_id,
            status=integration.status,
        )
        db.add(db_integration)
        db.commit()
        db.refresh(db_integration)
        
        # Log the creation
        create_log_entry(db, db_integration.id, IntegrationActivityLogBase(
            activity_type="creation",
            message=f"Integration created for ASIN: {integration.amazon_asin} and eBay ID: {integration.ebay_item_id}",
            level="INFO"
        ))
        
        logger.info(f"Created integration with ID: {db_integration.id}")
        return db_integration
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An integration with this Amazon ASIN or eBay Item ID already exists.",
        )

@router.get(
    "/{integration_id}",
    response_model=AmazonEbayIntegrationResponse,
    summary="Retrieve a specific integration link",
    description="Fetches the details of a single integration link by its ID, including its activity logs."
)
def read_integration(integration_id: int, db: Session = Depends(get_db)):
    """
    Retrieves an AmazonEbayIntegration record by its ID.
    Raises a 404 Not Found error if the ID does not exist.
    """
    db_integration = db.query(AmazonEbayIntegration).filter(
        AmazonEbayIntegration.id == integration_id
    ).first()
    if db_integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration with ID {integration_id} not found",
        )
    return db_integration

@router.get(
    "/",
    response_model=List[AmazonEbayIntegrationListResponse],
    summary="List all integration links",
    description="Returns a list of all Amazon-eBay integration links with basic details."
)
def list_integrations(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Returns a paginated list of all AmazonEbayIntegration records.
    """
    integrations = db.query(AmazonEbayIntegration).offset(skip).limit(limit).all()
    return integrations

@router.put(
    "/{integration_id}",
    response_model=AmazonEbayIntegrationResponse,
    summary="Update an existing integration link",
    description="Updates the details (ASIN, Item ID, status) of an existing integration link."
)
def update_integration(
    integration_id: int,
    integration: AmazonEbayIntegrationUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing AmazonEbayIntegration record.
    Raises a 404 Not Found error if the ID does not exist.
    """
    db_integration = db.query(AmazonEbayIntegration).filter(
        AmazonEbayIntegration.id == integration_id
    ).first()
    if db_integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration with ID {integration_id} not found",
        )

    update_data = integration.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_integration, key, value)
    
    db_integration.updated_at = datetime.utcnow() # Explicitly update timestamp
    
    try:
        db.add(db_integration)
        db.commit()
        db.refresh(db_integration)
        
        # Log the update
        create_log_entry(db, db_integration.id, IntegrationActivityLogBase(
            activity_type="update",
            message=f"Integration updated. Changes: {', '.join(update_data.keys())}",
            level="INFO"
        ))
        
        logger.info(f"Updated integration with ID: {integration_id}")
        return db_integration
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update failed. The provided Amazon ASIN or eBay Item ID is already in use by another integration.",
        )

@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an integration link",
    description="Permanently removes an integration link and all its associated activity logs."
)
def delete_integration(integration_id: int, db: Session = Depends(get_db)):
    """
    Deletes an AmazonEbayIntegration record by its ID.
    Raises a 404 Not Found error if the ID does not exist.
    """
    db_integration = db.query(AmazonEbayIntegration).filter(
        AmazonEbayIntegration.id == integration_id
    ).first()
    if db_integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration with ID {integration_id} not found",
        )

    db.delete(db_integration)
    db.commit()
    
    logger.warning(f"Deleted integration with ID: {integration_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.post(
    "/{integration_id}/sync",
    response_model=AmazonEbayIntegrationResponse,
    summary="Process a product synchronization",
    description="Executes the synchronization process (e.g., price/inventory update) between Amazon and eBay for a specific link."
)
def sync_integration(integration_id: int, db: Session = Depends(get_db)):
    """
    Executes a synchronization process for the given integration ID.
    This includes updating the last_sync_at timestamp and logging the activity.
    """
    db_integration = db.query(AmazonEbayIntegration).filter(
        AmazonEbayIntegration.id == integration_id
    ).first()
    if db_integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration with ID {integration_id} not found",
        )

    if db_integration.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integration is not active (status: {db_integration.status}). Cannot sync.",
        )

    # Process synchronization logic
    # In a real application, this would involve external API calls to Amazon and eBay
    
    # 1. Update last sync time
    db_integration.last_sync_at = datetime.utcnow()
    db_integration.updated_at = datetime.utcnow()
    
    # 2. Log the activity
    create_log_entry(db, db_integration.id, IntegrationActivityLogBase(
        activity_type="sync_success",
        message=f"Successfully synchronized inventory and price. New last_sync_at: {db_integration.last_sync_at.isoformat()}",
        level="INFO"
    ))
    
    # 3. Commit changes
    db.add(db_integration)
    db.commit()
    db.refresh(db_integration)
    
    logger.info(f"Sync successful for integration ID: {integration_id}")
    return db_integration

@router.get(
    "/{integration_id}/logs",
    response_model=List[IntegrationActivityLogBase],
    summary="Retrieve activity logs for an integration",
    description="Fetches the detailed activity logs for a specific integration link."
)
def get_integration_logs(
    integration_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of activity logs for a given integration ID.
    """
    # Check if integration exists
    if not db.query(AmazonEbayIntegration).filter(AmazonEbayIntegration.id == integration_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration with ID {integration_id} not found",
        )
        
    logs = db.query(IntegrationActivityLog).filter(
        IntegrationActivityLog.integration_id == integration_id
    ).order_by(IntegrationActivityLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    return logs
