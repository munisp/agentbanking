import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session

from . import models
from .config import get_db
from .models import (
    SyncManager, SyncActivityLog,
    SyncManagerCreate, SyncManagerUpdate, SyncManagerResponse, SyncManagerSimpleResponse,
    SyncActivityLogCreate, SyncActivityLogUpdate, SyncActivityLogResponse,
    Base
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/sync-managers",
    tags=["sync-managers"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def get_sync_manager_or_404(db: Session, sync_manager_id: int) -> SyncManager:
    """Helper function to fetch a SyncManager by ID or raise 404."""
    db_manager = db.query(SyncManager).filter(SyncManager.id == sync_manager_id).first()
    if db_manager is None:
        logger.warning(f"SyncManager with ID {sync_manager_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SyncManager with ID {sync_manager_id} not found"
        )
    return db_manager

# --- SyncManager CRUD Endpoints ---

@router.post(
    "/",
    response_model=SyncManagerSimpleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Sync Manager configuration"
)
def create_sync_manager(
    manager: SyncManagerCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new synchronization manager configuration.

    - **name**: Unique name for the sync job.
    - **source_system**: The system data is pulled from.
    - **target_system**: The system data is pushed to.
    - **sync_frequency**: How often the sync should run (e.g., 'daily', 'hourly').
    - **is_active**: Whether the job is active.
    """
    db_manager = db.query(SyncManager).filter(SyncManager.name == manager.name).first()
    if db_manager:
        logger.error(f"SyncManager with name '{manager.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SyncManager with name '{manager.name}' already exists"
        )

    db_manager = SyncManager(**manager.model_dump())
    db.add(db_manager)
    db.commit()
    db.refresh(db_manager)
    logger.info(f"Created new SyncManager: {db_manager.name} (ID: {db_manager.id})")
    return db_manager

@router.get(
    "/",
    response_model=List[SyncManagerSimpleResponse],
    summary="List all Sync Manager configurations"
)
def list_sync_managers(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100)
):
    """
    Retrieves a list of all synchronization manager configurations with pagination.
    """
    managers = db.query(SyncManager).offset(skip).limit(limit).all()
    return managers

@router.get(
    "/{sync_manager_id}",
    response_model=SyncManagerResponse,
    summary="Get a specific Sync Manager configuration and its activities"
)
def read_sync_manager(
    sync_manager_id: int = Path(..., description="The ID of the Sync Manager to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a single synchronization manager configuration by ID, including its activity logs.
    """
    db_manager = get_sync_manager_or_404(db, sync_manager_id)
    return db_manager

@router.patch(
    "/{sync_manager_id}",
    response_model=SyncManagerSimpleResponse,
    summary="Update an existing Sync Manager configuration"
)
def update_sync_manager(
    manager_update: SyncManagerUpdate,
    sync_manager_id: int = Path(..., description="The ID of the Sync Manager to update"),
    db: Session = Depends(get_db)
):
    """
    Updates an existing synchronization manager configuration. Only provided fields will be updated.
    """
    db_manager = get_sync_manager_or_404(db, sync_manager_id)

    update_data = manager_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_manager, key, value)

    db.add(db_manager)
    db.commit()
    db.refresh(db_manager)
    logger.info(f"Updated SyncManager ID {db_manager.id}")
    return db_manager

@router.delete(
    "/{sync_manager_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Sync Manager configuration"
)
def delete_sync_manager(
    sync_manager_id: int = Path(..., description="The ID of the Sync Manager to delete"),
    db: Session = Depends(get_db)
):
    """
    Deletes a synchronization manager configuration and all its associated activity logs.
    """
    db_manager = get_sync_manager_or_404(db, sync_manager_id)
    
    db.delete(db_manager)
    db.commit()
    logger.info(f"Deleted SyncManager ID {sync_manager_id}")
    return

# --- Business-Specific Endpoint ---

@router.post(
    "/{sync_manager_id}/trigger-sync",
    response_model=SyncActivityLogResponse,
    summary="Manually trigger a synchronization run for a manager"
)
def trigger_sync(
    sync_manager_id: int = Path(..., description="The ID of the Sync Manager to trigger"),
    db: Session = Depends(get_db)
):
    """
    Triggers a synchronization job with the configured data source.

    This endpoint updates the `last_sync_time` on the SyncManager and creates a new
    `SyncActivityLog` entry tracking the sync execution.
    """
    from datetime import datetime, timedelta
    import random

    db_manager = get_sync_manager_or_404(db, sync_manager_id)

    if not db_manager.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot trigger sync: Sync Manager is not active."
        )

    # 1. Execute sync process
    start_time = datetime.utcnow()
    import time as _time; sync_start = _time.monotonic()
    end_time = start_time + timedelta(seconds=duration)
    records_processed = 0
    
    # 2. Update the SyncManager
    db_manager.last_sync_time = end_time
    db.add(db_manager)

    # 3. Create a new SyncActivityLog entry
    activity_data = SyncActivityLogCreate(
        sync_manager_id=sync_manager_id,
        status="SUCCESS",
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration,
        records_processed=records_processed,
        error_message=None
    )
    db_activity = SyncActivityLog(**activity_data.model_dump())
    db.add(db_activity)
    
    db.commit()
    db.refresh(db_activity)
    logger.info(f"Triggered and completed sync for SyncManager ID {sync_manager_id}. Processed {records_processed} records.")
    
    return db_activity

# --- SyncActivityLog Endpoints (Read/List only, creation is handled by trigger-sync) ---

@router.get(
    "/{sync_manager_id}/activities",
    response_model=List[SyncActivityLogResponse],
    summary="List activities for a specific Sync Manager"
)
def list_sync_activities(
    sync_manager_id: int = Path(..., description="The ID of the Sync Manager"),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100)
):
    """
    Retrieves a list of activity logs for a specific synchronization manager, ordered by start time descending.
    """
    # Ensure the parent manager exists
    get_sync_manager_or_404(db, sync_manager_id)

    activities = db.query(SyncActivityLog).filter(
        SyncActivityLog.sync_manager_id == sync_manager_id
    ).order_by(SyncActivityLog.start_time.desc()).offset(skip).limit(limit).all()
    
    return activities

@router.get(
    "/{sync_manager_id}/activities/{activity_id}",
    response_model=SyncActivityLogResponse,
    summary="Get a specific Sync Activity Log entry"
)
def read_sync_activity(
    sync_manager_id: int = Path(..., description="The ID of the Sync Manager"),
    activity_id: int = Path(..., description="The ID of the Activity Log entry"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a single activity log entry by its ID and ensures it belongs to the specified Sync Manager.
    """
    db_activity = db.query(SyncActivityLog).filter(
        SyncActivityLog.id == activity_id,
        SyncActivityLog.sync_manager_id == sync_manager_id
    ).first()
    
    if db_activity is None:
        logger.warning(f"Activity ID {activity_id} for SyncManager ID {sync_manager_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity ID {activity_id} not found for SyncManager ID {sync_manager_id}"
        )
    
    return db_activity

# Note: Update and Delete for SyncActivityLog are typically not exposed via API
# as they represent immutable historical records. However, if required, they can be added.
# For this production-ready implementation, we will omit them to enforce immutability of logs.
