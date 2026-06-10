import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db
from .models import DataAsset, ActivityLog, DataAssetCreate, DataAssetUpdate, DataAssetResponse, ActivityLogResponse, DataAssetWithLogsResponse

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Router Initialization ---
router = APIRouter(
    prefix="/data-assets",
    tags=["Data Assets"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(db: Session, asset_id: uuid.UUID, action: str, user_id: str, details: Optional[dict] = None):
    """
    Creates an activity log entry for a data asset operation.
    """
    log_entry = ActivityLog(
        data_asset_id=asset_id,
        action=action,
        user_id=user_id,
        details=details or {}
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Activity logged for asset {asset_id}: {action} by {user_id}")

# --- CRUD Endpoints for DataAsset ---

@router.post(
    "/",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Data Asset",
    description="Registers a new data asset (e.g., a table, file, or stream) in the lakehouse catalog."
)
def create_data_asset(
    asset: DataAssetCreate,
    db: Session = Depends(get_db),
    user_id: str = Query("system_user", description="Identifier of the user or system performing the action")
):
    """
    Creates a new DataAsset record in the database.
    """
    db_asset = DataAsset(**asset.model_dump())
    try:
        db.add(db_asset)
        db.commit()
        db.refresh(db_asset)
        log_activity(db, db_asset.id, "CREATE", user_id, {"initial_path": db_asset.storage_path})
        return db_asset
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating asset: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data Asset with this storage path or name already exists."
        )

@router.get(
    "/",
    response_model=List[DataAssetResponse],
    summary="List all Data Assets",
    description="Retrieves a list of all registered data assets, optionally filtered by type and activity status."
)
def list_data_assets(
    db: Session = Depends(get_db),
    asset_type: Optional[str] = Query(None, description="Filter by asset type (e.g., 'table', 'file')"),
    is_active: Optional[bool] = Query(True, description="Filter by active status")
):
    """
    Retrieves a list of DataAsset records.
    """
    query = db.query(DataAsset)
    if asset_type:
        query = query.filter(DataAsset.asset_type == asset_type)
    if is_active is not None:
        query = query.filter(DataAsset.is_active == is_active)
        
    return query.all()

@router.get(
    "/{asset_id}",
    response_model=DataAssetResponse,
    summary="Get a Data Asset by ID",
    description="Retrieves the details of a specific data asset using its unique ID."
)
def read_data_asset(asset_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single DataAsset record by ID.
    """
    db_asset = db.query(DataAsset).filter(DataAsset.id == asset_id).first()
    if db_asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data Asset not found")
    return db_asset

@router.put(
    "/{asset_id}",
    response_model=DataAssetResponse,
    summary="Update a Data Asset",
    description="Updates the details of an existing data asset."
)
def update_data_asset(
    asset_id: uuid.UUID,
    asset: DataAssetUpdate,
    db: Session = Depends(get_db),
    user_id: str = Query("system_user", description="Identifier of the user or system performing the action")
):
    """
    Updates an existing DataAsset record.
    """
    db_asset = db.query(DataAsset).filter(DataAsset.id == asset_id).first()
    if db_asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data Asset not found")

    update_data = asset.model_dump(exclude_unset=True)
    
    # Check for changes to log
    changes = {k: v for k, v in update_data.items() if getattr(db_asset, k) != v}
    
    for key, value in update_data.items():
        setattr(db_asset, key, value)

    try:
        db.commit()
        db.refresh(db_asset)
        if changes:
            log_activity(db, db_asset.id, "UPDATE", user_id, {"changes": changes})
        return db_asset
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating asset {asset_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update failed due to a conflict (e.g., storage path already in use)."
        )

@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Data Asset",
    description="Marks a data asset as inactive (soft delete) or permanently deletes it and its associated logs."
)
def delete_data_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Query("system_user", description="Identifier of the user or system performing the action"),
    hard_delete: bool = Query(False, description="If true, permanently deletes the record and all logs.")
):
    """
    Deletes a DataAsset record (soft or hard delete).
    """
    db_asset = db.query(DataAsset).filter(DataAsset.id == asset_id).first()
    if db_asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data Asset not found")

    if hard_delete:
        db.delete(db_asset)
        log_action = "HARD_DELETE"
    else:
        db_asset.is_active = False
        log_action = "SOFT_DELETE"

    db.commit()
    log_activity(db, asset_id, log_action, user_id)
    return

# --- Business-Specific Endpoint ---

@router.patch(
    "/{asset_id}/schema",
    response_model=DataAssetResponse,
    summary="Update Data Asset Schema",
    description="Updates only the schema definition of a data asset, which is a common lakehouse operation."
)
def update_asset_schema(
    asset_id: uuid.UUID,
    new_schema: dict,
    db: Session = Depends(get_db),
    user_id: str = Query("system_user", description="Identifier of the user or system performing the action")
):
    """
    Updates the schema_definition field of a DataAsset.
    """
    db_asset = db.query(DataAsset).filter(DataAsset.id == asset_id).first()
    if db_asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data Asset not found")

    old_schema = db_asset.schema_definition
    db_asset.schema_definition = new_schema
    
    db.commit()
    db.refresh(db_asset)
    
    log_activity(db, asset_id, "UPDATE_SCHEMA", user_id, {"old_schema_keys": list(old_schema.keys()) if old_schema else [], "new_schema_keys": list(new_schema.keys())})
    return db_asset

# --- ActivityLog Endpoints ---

@router.get(
    "/{asset_id}/logs",
    response_model=List[ActivityLogResponse],
    summary="Get Activity Logs for a Data Asset",
    description="Retrieves the historical activity log for a specific data asset."
)
def get_asset_activity_logs(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieves activity logs associated with a specific DataAsset.
    """
    # Ensure the asset exists before querying logs
    if not db.query(DataAsset).filter(DataAsset.id == asset_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data Asset not found")

    logs = db.query(ActivityLog).filter(ActivityLog.data_asset_id == asset_id).order_by(ActivityLog.timestamp.desc()).limit(limit).offset(offset).all()
    return logs

@router.get(
    "/logs",
    response_model=List[ActivityLogResponse],
    summary="List Recent Activity Logs",
    description="Retrieves a list of the most recent activity logs across all data assets."
)
def list_recent_activity_logs(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieves a list of the most recent ActivityLog records.
    """
    logs = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(limit).offset(offset).all()
    return logs
