import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from . import models
from .config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the router
router = APIRouter(
    prefix="/data-warehouse",
    tags=["data-warehouse"],
    responses={404: {"description": "Not found"}},
)

# Placeholder for the user/service performing the action (for activity logging)
# In a real application, this would come from an authentication dependency
CURRENT_USER_ID = 1

# --- Helper Functions for DB Operations and Logging ---

def create_activity_log(db: Session, data_warehouse_id: int, activity_type: str, details: Optional[str] = None):
    """Creates an activity log entry."""
    log_entry = models.DataWarehouseActivityLog(
        data_warehouse_id=data_warehouse_id,
        activity_type=activity_type,
        details=details,
        performed_by_user_id=CURRENT_USER_ID
    )
    db.add(log_entry)
    # Note: The log entry will be committed with the main transaction

def get_data_warehouse_by_id(db: Session, dw_id: int) -> models.DataWarehouse:
    """Fetches a DataWarehouse asset by ID or raises 404."""
    dw_asset = db.get(models.DataWarehouse, dw_id)
    if not dw_asset:
        logger.warning(f"DataWarehouse asset with ID {dw_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataWarehouse asset with ID {dw_id} not found"
        )
    return dw_asset

# --- CRUD Endpoints for DataWarehouse ---

@router.post(
    "/", 
    response_model=models.DataWarehouseResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Data Warehouse asset"
)
def create_data_warehouse(
    dw_in: models.DataWarehouseCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new Data Warehouse asset with the provided details.
    
    Raises:
    - 409 Conflict: If an asset with the same name already exists.
    """
    try:
        # Check for existing asset with the same name
        existing_dw = db.execute(
            select(models.DataWarehouse).where(models.DataWarehouse.name == dw_in.name)
        ).scalar_one_or_none()
        
        if existing_dw:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"DataWarehouse asset with name '{dw_in.name}' already exists."
            )

        dw_asset = models.DataWarehouse(**dw_in.model_dump())
        db.add(dw_asset)
        
        # Create activity log
        db.flush() # Flush to get the ID for the new asset
        create_activity_log(db, dw_asset.id, "CREATE", f"Asset created by user {CURRENT_USER_ID}")
        
        db.commit()
        db.refresh(dw_asset)
        logger.info(f"Created DataWarehouse asset: ID {dw_asset.id}, Name '{dw_asset.name}'")
        return dw_asset
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data provided or integrity constraint violated."
        )
    except HTTPException:
        raise # Re-raise 409
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during asset creation."
        )

@router.get(
    "/{dw_id}", 
    response_model=models.DataWarehouseResponse,
    summary="Retrieve a specific Data Warehouse asset"
)
def read_data_warehouse(
    dw_id: int = Path(..., description="The ID of the Data Warehouse asset to retrieve"), 
    db: Session = Depends(get_db)
):
    """
    Retrieves the details of a single Data Warehouse asset by its ID.
    
    Raises:
    - 404 Not Found: If the asset does not exist.
    """
    dw_asset = get_data_warehouse_by_id(db, dw_id)
    
    # Create activity log for access
    create_activity_log(db, dw_id, "ACCESS", f"Asset read by user {CURRENT_USER_ID}")
    db.commit()
    
    return dw_asset

@router.get(
    "/", 
    response_model=List[models.DataWarehouseResponse],
    summary="List all Data Warehouse assets"
)
def list_data_warehouse(
    skip: int = Query(0, ge=0, description="Number of items to skip (offset)"),
    limit: int = Query(100, le=1000, description="Maximum number of items to return (limit)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    owner_id: Optional[int] = Query(None, description="Filter by owner ID"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of Data Warehouse assets, with optional filtering.
    """
    stmt = select(models.DataWarehouse)
    
    if is_active is not None:
        stmt = stmt.where(models.DataWarehouse.is_active == is_active)
    
    if owner_id is not None:
        stmt = stmt.where(models.DataWarehouse.owner_id == owner_id)
        
    dw_assets = db.execute(stmt.offset(skip).limit(limit)).scalars().all()
    
    return dw_assets

@router.put(
    "/{dw_id}", 
    response_model=models.DataWarehouseResponse,
    summary="Update an existing Data Warehouse asset"
)
def update_data_warehouse(
    dw_id: int = Path(..., description="The ID of the Data Warehouse asset to update"),
    dw_in: models.DataWarehouseUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing Data Warehouse asset.
    
    Raises:
    - 404 Not Found: If the asset does not exist.
    - 409 Conflict: If the new name conflicts with an existing asset.
    """
    dw_asset = get_data_warehouse_by_id(db, dw_id)
    
    update_data = dw_in.model_dump(exclude_unset=True)
    
    if "name" in update_data and update_data["name"] != dw_asset.name:
        # Check for name conflict
        existing_dw = db.execute(
            select(models.DataWarehouse)
            .where(models.DataWarehouse.name == update_data["name"])
            .where(models.DataWarehouse.id != dw_id)
        ).scalar_one_or_none()
        
        if existing_dw:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"DataWarehouse asset with name '{update_data['name']}' already exists."
            )

    # Apply updates
    for key, value in update_data.items():
        setattr(dw_asset, key, value)

    try:
        # Create activity log
        create_activity_log(db, dw_id, "UPDATE", f"Asset updated by user {CURRENT_USER_ID}. Changes: {list(update_data.keys())}")
        
        db.add(dw_asset)
        db.commit()
        db.refresh(dw_asset)
        logger.info(f"Updated DataWarehouse asset: ID {dw_asset.id}, Name '{dw_asset.name}'")
        return dw_asset
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during update: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data provided or integrity constraint violated."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during asset update."
        )

@router.delete(
    "/{dw_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Data Warehouse asset"
)
def delete_data_warehouse(
    dw_id: int = Path(..., description="The ID of the Data Warehouse asset to delete"), 
    db: Session = Depends(get_db)
):
    """
    Deletes a Data Warehouse asset by its ID.
    
    Raises:
    - 404 Not Found: If the asset does not exist.
    """
    dw_asset = get_data_warehouse_by_id(db, dw_id)
    
    # Create activity log before deletion (will be deleted by CASCADE, but useful for immediate context)
    # In a real system, this log might be written to a separate, non-cascading table or external system
    create_activity_log(db, dw_id, "DELETE", f"Asset deleted by user {CURRENT_USER_ID}")
    
    db.delete(dw_asset)
    db.commit()
    logger.info(f"Deleted DataWarehouse asset: ID {dw_id}")
    return

# --- Business-Specific Endpoints ---

@router.get(
    "/{dw_id}/logs",
    response_model=List[models.DataWarehouseActivityLogResponse],
    summary="Retrieve activity logs for a specific Data Warehouse asset"
)
def get_data_warehouse_logs(
    dw_id: int = Path(..., description="The ID of the Data Warehouse asset"),
    skip: int = Query(0, ge=0, description="Number of logs to skip (offset)"),
    limit: int = Query(100, le=1000, description="Maximum number of logs to return (limit)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of activity logs for a specified Data Warehouse asset.
    
    Raises:
    - 404 Not Found: If the asset does not exist.
    """
    # Check if the DataWarehouse asset exists
    get_data_warehouse_by_id(db, dw_id)
    
    # Fetch logs
    stmt = (
        select(models.DataWarehouseActivityLog)
        .where(models.DataWarehouseActivityLog.data_warehouse_id == dw_id)
        .order_by(models.DataWarehouseActivityLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    
    logs = db.execute(stmt).scalars().all()
    
    return logs

@router.post(
    "/{dw_id}/deactivate",
    response_model=models.DataWarehouseResponse,
    summary="Deactivate a Data Warehouse asset"
)
def deactivate_data_warehouse(
    dw_id: int = Path(..., description="The ID of the Data Warehouse asset to deactivate"),
    db: Session = Depends(get_db)
):
    """
    Sets the `is_active` flag of a Data Warehouse asset to `False`.
    
    Raises:
    - 404 Not Found: If the asset does not exist.
    """
    dw_asset = get_data_warehouse_by_id(db, dw_id)
    
    if not dw_asset.is_active:
        return dw_asset # Already deactivated, return current state
        
    dw_asset.is_active = False
    
    # Create activity log
    create_activity_log(db, dw_id, "DEACTIVATE", f"Asset deactivated by user {CURRENT_USER_ID}")
    
    db.add(dw_asset)
    db.commit()
    db.refresh(dw_asset)
    logger.info(f"Deactivated DataWarehouse asset: ID {dw_asset.id}")
    return dw_asset
