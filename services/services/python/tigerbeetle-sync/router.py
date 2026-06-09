import logging
import os
import uuid
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_db
from models import (
    TigerBeetleSync,
    TigerBeetleSyncActivityLog,
    TigerBeetleSyncActivityLogCreate,
    TigerBeetleSyncCreate,
    TigerBeetleSyncResponse,
    TigerBeetleSyncUpdate,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SYNC_MANAGER_URL = os.getenv("SYNC_MANAGER_URL", "http://localhost:8085")

# --- Router Setup ---
router = APIRouter(
    prefix="/tigerbeetle-sync",
    tags=["TigerBeetle Sync"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_sync_config_or_404(db: Session, sync_id: uuid.UUID) -> TigerBeetleSync:
    """
    Fetches a TigerBeetleSync configuration by ID or raises a 404 error.
    """
    sync_config = db.query(TigerBeetleSync).filter(TigerBeetleSync.id == sync_id).first()
    if not sync_config:
        logger.warning(f"TigerBeetleSync with ID {sync_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync configuration with ID {sync_id} not found",
        )
    return sync_config

# --- CRUD Endpoints for TigerBeetleSync ---

@router.post(
    "/",
    response_model=TigerBeetleSyncResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new TigerBeetle Sync Configuration",
)
def create_sync_config(
    sync_config: TigerBeetleSyncCreate, db: Session = Depends(get_db)
):
    """
    Creates a new configuration for a TigerBeetle synchronization job.
    """
    db_sync_config = TigerBeetleSync(**sync_config.model_dump())
    db.add(db_sync_config)
    db.commit()
    db.refresh(db_sync_config)
    logger.info(f"Created new sync config: {db_sync_config.id}")
    return db_sync_config


@router.get(
    "/{sync_id}",
    response_model=TigerBeetleSyncResponse,
    summary="Get a TigerBeetle Sync Configuration by ID",
)
def read_sync_config(sync_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a specific TigerBeetle Sync Configuration using its unique ID.
    """
    return get_sync_config_or_404(db, sync_id)


@router.get(
    "/",
    response_model=List[TigerBeetleSyncResponse],
    summary="List all TigerBeetle Sync Configurations",
)
def list_sync_configs(
    db: Session = Depends(get_db), skip: int = 0, limit: int = 100
):
    """
    Retrieves a list of all TigerBeetle Sync Configurations with pagination.
    """
    sync_configs = db.query(TigerBeetleSync).offset(skip).limit(limit).all()
    return sync_configs


@router.patch(
    "/{sync_id}",
    response_model=TigerBeetleSyncResponse,
    summary="Update an existing TigerBeetle Sync Configuration",
)
def update_sync_config(
    sync_id: uuid.UUID,
    sync_config_update: TigerBeetleSyncUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing TigerBeetle Sync Configuration. Only provided fields will be updated.
    """
    db_sync_config = get_sync_config_or_404(db, sync_id)

    update_data = sync_config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_sync_config, key, value)

    db.add(db_sync_config)
    db.commit()
    db.refresh(db_sync_config)
    logger.info(f"Updated sync config: {sync_id}")
    return db_sync_config


@router.delete(
    "/{sync_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a TigerBeetle Sync Configuration",
)
def delete_sync_config(sync_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes a TigerBeetle Sync Configuration and all associated activity logs.
    """
    db_sync_config = get_sync_config_or_404(db, sync_id)
    db.delete(db_sync_config)
    db.commit()
    logger.info(f"Deleted sync config: {sync_id}")
    return {"ok": True}


# --- Business-Specific Endpoints ---

@router.post(
    "/{sync_id}/start",
    response_model=TigerBeetleSyncResponse,
    summary="Start a synchronization job",
)
def start_sync(sync_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Marks the sync configuration status as 'ACTIVE', triggers the Go sync manager,
    and logs the start event.
    """
    db_sync_config = get_sync_config_or_404(db, sync_id)
    
    db_sync_config.status = "ACTIVE"
    db.add(db_sync_config)
    
    trigger_result = "not_triggered"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{SYNC_MANAGER_URL}/api/v1/sync/trigger")
            if resp.status_code == 200:
                trigger_result = "triggered"
            else:
                trigger_result = f"failed_status_{resp.status_code}"
    except Exception as e:
        trigger_result = f"unreachable: {e}"
        logger.warning(f"Could not trigger Go sync manager: {e}")
    
    log_entry = TigerBeetleSyncActivityLog(
        sync_id=sync_id,
        log_level="INFO",
        message=f"Synchronization job started. Go sync manager: {trigger_result}",
    )
    db.add(log_entry)
    
    db.commit()
    db.refresh(db_sync_config)
    logger.info(f"Started sync job for config: {sync_id}, trigger: {trigger_result}")
    return db_sync_config


@router.post(
    "/{sync_id}/pause",
    response_model=TigerBeetleSyncResponse,
    summary="Pause a synchronization job",
)
def pause_sync(sync_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Marks the sync configuration status as 'PAUSED' and logs the pause event.
    """
    db_sync_config = get_sync_config_or_404(db, sync_id)
    
    # Update status
    db_sync_config.status = "PAUSED"
    db.add(db_sync_config)
    
    # Log activity
    log_entry = TigerBeetleSyncActivityLog(
        sync_id=sync_id,
        log_level="WARNING",
        message="Synchronization job paused by user/system.",
    )
    db.add(log_entry)
    
    db.commit()
    db.refresh(db_sync_config)
    logger.info(f"Paused sync job for config: {sync_id}")
    return db_sync_config


@router.post(
    "/{sync_id}/log",
    status_code=status.HTTP_201_CREATED,
    summary="Log an activity for a sync configuration",
)
def log_sync_activity(
    sync_id: uuid.UUID,
    log_data: TigerBeetleSyncActivityLogBase,
    db: Session = Depends(get_db),
):
    """
    Creates a new activity log entry associated with a specific sync configuration.
    """
    # Check if sync config exists
    get_sync_config_or_404(db, sync_id)
    
    log_entry = TigerBeetleSyncActivityLog(
        sync_id=sync_id,
        log_level=log_data.log_level,
        message=log_data.message,
        details=log_data.details,
    )
    db.add(log_entry)
    db.commit()
    logger.info(f"Logged activity for sync config {sync_id}: {log_data.message}")
    return {"message": "Activity logged successfully"}
