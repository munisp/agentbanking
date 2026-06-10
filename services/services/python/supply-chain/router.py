import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db, init_db

# Initialize the database (create tables)
init_db()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/supply-chain",
    tags=["supply-chain"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_item_by_id(db: Session, item_id: int) -> models.SupplyChainItem:
    """
    Fetches a SupplyChainItem by its ID, raising 404 if not found.
    """
    item = db.query(models.SupplyChainItem).filter(models.SupplyChainItem.id == item_id).first()
    if not item:
        logger.warning(f"SupplyChainItem with ID {item_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SupplyChainItem with ID {item_id} not found"
        )
    return item

def create_activity_log(db: Session, item_id: int, activity_type: str, details: Optional[str] = None):
    """
    Creates a new ActivityLog entry for a given item.
    """
    log_data = models.ActivityLogCreate(
        item_id=item_id,
        activity_type=activity_type,
        details=details
    )
    db_log = models.ActivityLog(**log_data.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

# --- CRUD Endpoints for SupplyChainItem ---

@router.post(
    "/items/",
    response_model=models.SupplyChainItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Supply Chain Item",
    description="Registers a new item or batch into the supply chain tracking system."
)
def create_item(item: models.SupplyChainItemCreate, db: Session = Depends(get_db)):
    """
    Creates a new SupplyChainItem in the database.
    """
    try:
        db_item = models.SupplyChainItem(**item.model_dump())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        
        # Log the creation activity
        create_activity_log(
            db, 
            db_item.id, 
            activity_type="ITEM_CREATED", 
            details=f"Item {db_item.name} (SKU: {db_item.sku}) registered."
        )
        
        logger.info(f"Created new SupplyChainItem with ID: {db_item.id}")
        return db_item
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during item creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU already exists or other integrity constraint violated."
        )

@router.get(
    "/items/{item_id}",
    response_model=models.SupplyChainItemResponse,
    summary="Get a Supply Chain Item by ID",
    description="Retrieves the details and full activity log for a specific supply chain item."
)
def read_item(item_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a SupplyChainItem by its ID.
    """
    # Uses eager loading for activity_logs to return the full response model
    item = db.query(models.SupplyChainItem).filter(models.SupplyChainItem.id == item_id).first()
    return get_item_by_id(db, item_id)

@router.get(
    "/items/",
    response_model=List[models.SupplyChainItemSimpleResponse],
    summary="List all Supply Chain Items",
    description="Retrieves a paginated list of all supply chain items."
)
def list_items(
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)."),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of items to return."),
    db: Session = Depends(get_db)
):
    """
    Lists all SupplyChainItems with optional pagination.
    """
    items = db.query(models.SupplyChainItem).offset(skip).limit(limit).all()
    return items

@router.put(
    "/items/{item_id}",
    response_model=models.SupplyChainItemResponse,
    summary="Update a Supply Chain Item",
    description="Updates the details of an existing supply chain item."
)
def update_item(item_id: int, item_update: models.SupplyChainItemUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing SupplyChainItem.
    """
    db_item = get_item_by_id(db, item_id)
    
    update_data = item_update.model_dump(exclude_unset=True)
    
    # Check if any fields are actually being updated
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update."
        )

    for key, value in update_data.items():
        setattr(db_item, key, value)

    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        
        # Log the update activity
        create_activity_log(
            db, 
            db_item.id, 
            activity_type="ITEM_UPDATED", 
            details=f"Item details updated. Fields changed: {', '.join(update_data.keys())}"
        )
        
        logger.info(f"Updated SupplyChainItem with ID: {item_id}")
        return db_item
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during item update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU already exists or other integrity constraint violated."
        )

@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Supply Chain Item",
    description="Deletes a supply chain item and all associated activity logs."
)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """
    Deletes a SupplyChainItem by its ID.
    """
    db_item = get_item_by_id(db, item_id)
    
    db.delete(db_item)
    db.commit()
    
    logger.info(f"Deleted SupplyChainItem with ID: {item_id}")
    return

# --- Business Logic Endpoints ---

class ItemActivity(models.Config):
    """Schema for logging a new activity and optionally updating status/location."""
    new_status: Optional[models.ItemStatus] = Field(None, description="New status of the item.")
    new_location: Optional[str] = Field(None, max_length=255, description="New location of the item.")
    activity_type: str = Field(..., description="Type of activity being logged (e.g., SCAN, INSPECTION).")
    details: Optional[str] = Field(None, description="Detailed description of the activity.")

@router.post(
    "/items/{item_id}/log_activity",
    response_model=models.SupplyChainItemResponse,
    summary="Log Activity and Update Item Status/Location",
    description="Logs a new activity for an item and optionally updates its status and/or current location."
)
def log_item_activity(item_id: int, activity: ItemActivity, db: Session = Depends(get_db)):
    """
    Logs a new activity and updates the item's status and/or location if provided.
    """
    db_item = get_item_by_id(db, item_id)
    
    update_fields = []
    
    # 1. Update status if provided
    if activity.new_status is not None and activity.new_status.value != db_item.status:
        db_item.status = activity.new_status.value
        update_fields.append(f"Status changed to {activity.new_status.value}")
        
    # 2. Update location if provided
    if activity.new_location is not None and activity.new_location != db_item.current_location:
        db_item.current_location = activity.new_location
        update_fields.append(f"Location changed to {activity.new_location}")

    # 3. Commit changes to the item
    if update_fields:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        
    # 4. Create the activity log
    log_details = activity.details if activity.details else "No specific details provided."
    if update_fields:
        log_details = f"{log_details} | Item updates: {'; '.join(update_fields)}"
        
    create_activity_log(
        db, 
        db_item.id, 
        activity_type=activity.activity_type, 
        details=log_details
    )
    
    logger.info(f"Logged activity for SupplyChainItem ID: {item_id}. Activity Type: {activity.activity_type}")
    
    # Refresh again to ensure the newly created log is included in the response
    db.refresh(db_item)
    return db_item
