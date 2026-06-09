from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from .config import get_db, logger
from .models import (
    OfflineSyncRecord,
    SyncActivityLog,
    OfflineSyncRecordCreate,
    OfflineSyncRecordUpdate,
    OfflineSyncRecordResponse,
    SyncActivityLogCreate,
    SyncActivityLogResponse,
)

router = APIRouter(
    prefix="/offline-sync",
    tags=["Offline Sync"],
    responses={404: {"description": "Not found"}},
)

# --- CRUD Endpoints for OfflineSyncRecord ---

@router.post(
    "/records",
    response_model=OfflineSyncRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new offline sync record",
    description="Adds a new record of an offline change (CREATE, UPDATE, or DELETE) that needs to be synchronized with the main system."
)
def create_sync_record(
    record: OfflineSyncRecordCreate, db: Session = Depends(get_db)
):
    """
    Creates a new OfflineSyncRecord in the database.
    """
    logger.info(f"Creating new sync record for entity_type: {record.entity_type}, operation: {record.operation}")
    
    db_record = OfflineSyncRecord(**record.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    
    logger.info(f"Successfully created sync record with ID: {db_record.id}")
    return db_record

@router.get(
    "/records/{record_id}",
    response_model=OfflineSyncRecordResponse,
    summary="Retrieve a specific offline sync record",
    description="Fetches the details of a single offline sync record by its ID."
)
def read_sync_record(record_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single OfflineSyncRecord by ID.
    """
    record = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.id == record_id).first()
    if record is None:
        logger.warning(f"Sync record with ID {record_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="OfflineSyncRecord not found"
        )
    return record

@router.get(
    "/records",
    response_model=List[OfflineSyncRecordResponse],
    summary="List all offline sync records",
    description="Retrieves a list of all offline sync records, with optional filtering and pagination."
)
def list_sync_records(
    status_filter: Optional[str] = Query(None, description="Filter by synchronization status (e.g., PENDING, FAILED)"),
    entity_type_filter: Optional[str] = Query(None, description="Filter by the type of entity being synchronized"),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """
    Retrieves a list of OfflineSyncRecords with filtering and pagination.
    """
    query = db.query(OfflineSyncRecord)
    
    if status_filter:
        query = query.filter(OfflineSyncRecord.status == status_filter.upper())
    
    if entity_type_filter:
        query = query.filter(OfflineSyncRecord.entity_type == entity_type_filter)
        
    records = query.offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(records)} sync records with filters: status={status_filter}, entity_type={entity_type_filter}")
    return records

@router.put(
    "/records/{record_id}",
    response_model=OfflineSyncRecordResponse,
    summary="Update an existing offline sync record",
    description="Updates the status, attempt count, or data payload of an existing offline sync record."
)
def update_sync_record(
    record_id: int, record_update: OfflineSyncRecordUpdate, db: Session = Depends(get_db)
):
    """
    Updates an existing OfflineSyncRecord.
    """
    db_record = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.id == record_id).first()
    if db_record is None:
        logger.warning(f"Attempted to update non-existent sync record with ID {record_id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="OfflineSyncRecord not found"
        )

    update_data = record_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_record, key, value)

    db.commit()
    db.refresh(db_record)
    
    logger.info(f"Successfully updated sync record with ID: {record_id}")
    return db_record

@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an offline sync record",
    description="Deletes a specific offline sync record by its ID. This is typically done after a successful synchronization."
)
def delete_sync_record(record_id: int, db: Session = Depends(get_db)):
    """
    Deletes an OfflineSyncRecord by ID.
    """
    db_record = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.id == record_id).first()
    if db_record is None:
        logger.warning(f"Attempted to delete non-existent sync record with ID {record_id}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="OfflineSyncRecord not found"
        )

    db.delete(db_record)
    db.commit()
    
    logger.info(f"Successfully deleted sync record with ID: {record_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.get(
    "/records/pending",
    response_model=List[OfflineSyncRecordResponse],
    summary="Get all pending sync records",
    description="Retrieves all records that are currently in 'PENDING' status, ready for synchronization."
)
def get_pending_records(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """
    Retrieves a list of OfflineSyncRecords with status 'PENDING'.
    """
    query = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.status == "PENDING").order_by(OfflineSyncRecord.created_at)
    
    if entity_type:
        query = query.filter(OfflineSyncRecord.entity_type == entity_type)
        
    records = query.limit(limit).all()
    
    logger.info(f"Retrieved {len(records)} pending sync records.")
    return records

@router.patch(
    "/records/{record_id}/mark-failed",
    response_model=OfflineSyncRecordResponse,
    summary="Mark a sync record as FAILED",
    description="Marks a record as 'FAILED' and increments the attempt count. Optionally logs the failure reason."
)
def mark_record_failed(
    record_id: int, 
    failure_message: str = Query(..., description="The reason for the synchronization failure."),
    db: Session = Depends(get_db)
):
    """
    Marks an OfflineSyncRecord as FAILED and logs the activity.
    """
    db_record = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.id == record_id).first()
    if db_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="OfflineSyncRecord not found"
        )

    db_record.status = "FAILED"
    db_record.attempt_count += 1
    
    # Log the failure activity
    log_entry = SyncActivityLog(
        sync_record_id=record_id,
        outcome="FAILURE",
        message=failure_message
    )
    db.add(log_entry)
    
    db.commit()
    db.refresh(db_record)
    
    logger.warning(f"Sync record {record_id} marked as FAILED. Reason: {failure_message}")
    return db_record

# --- CRUD Endpoints for SyncActivityLog ---

@router.post(
    "/records/{record_id}/activities",
    response_model=SyncActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a synchronization activity",
    description="Adds an entry to the activity log for a specific sync record."
)
def create_sync_activity_log(
    record_id: int, log_data: SyncActivityLogCreate, db: Session = Depends(get_db)
):
    """
    Creates a new SyncActivityLog entry.
    """
    # Ensure the record exists
    db_record = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.id == record_id).first()
    if db_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="OfflineSyncRecord not found"
        )
        
    # Override sync_record_id from path for consistency
    log_data.sync_record_id = record_id
    
    db_log = SyncActivityLog(**log_data.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    logger.info(f"Logged activity for sync record {record_id} with outcome: {log_data.outcome}")
    return db_log

@router.get(
    "/records/{record_id}/activities",
    response_model=List[SyncActivityLogResponse],
    summary="List activities for a sync record",
    description="Retrieves all synchronization activity logs associated with a specific offline sync record."
)
def list_sync_activities(record_id: int, db: Session = Depends(get_db)):
    """
    Retrieves all SyncActivityLogs for a given OfflineSyncRecord ID.
    """
    # Ensure the record exists
    db_record = db.query(OfflineSyncRecord).filter(OfflineSyncRecord.id == record_id).first()
    if db_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="OfflineSyncRecord not found"
        )
        
    activities = db.query(SyncActivityLog).filter(SyncActivityLog.sync_record_id == record_id).order_by(SyncActivityLog.timestamp.desc()).all()
    
    logger.info(f"Retrieved {len(activities)} activities for sync record {record_id}.")
    return activities

@router.get(
    "/stats/status-count",
    summary="Get count of records by status",
    description="Returns a dictionary with the count of offline sync records for each status (PENDING, SUCCESS, FAILED, etc.)."
)
def get_status_counts(db: Session = Depends(get_db)):
    """
    Returns a count of records grouped by their status.
    """
    counts = (
        db.query(OfflineSyncRecord.status, func.count(OfflineSyncRecord.id))
        .group_by(OfflineSyncRecord.status)
        .all()
    )
    
    result = {status: count for status, count in counts}
    logger.info(f"Retrieved status counts: {result}")
    return result
