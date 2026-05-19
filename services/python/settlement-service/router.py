import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

# Assuming config.py and models.py are in the same directory or accessible
from .config import get_db, get_settings
from .models import (
    Base, Settlement, SettlementLog, SettlementStatus, LogLevel,
    SettlementCreate, SettlementUpdate, SettlementResponse, SettlementLogCreate, SettlementLogResponse
)

# Initialize logger and settings
settings = get_settings()
logger = logging.getLogger(settings.SERVICE_NAME)

# Initialize FastAPI router
router = APIRouter(
    prefix="/settlements",
    tags=["settlements"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def get_settlement_by_id(db: Session, settlement_id: int) -> Settlement:
    """Helper function to fetch a settlement by ID or raise 404."""
    settlement = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not settlement:
        logger.warning(f"Settlement with ID {settlement_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settlement with ID {settlement_id} not found"
        )
    return settlement

def create_log_entry_internal(db: Session, settlement_id: int, log_data: SettlementLogCreate):
    """Internal function to create a log entry."""
    db_log = SettlementLog(
        settlement_id=settlement_id,
        level=log_data.level.value,
        message=log_data.message,
        details=log_data.details
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

# --- CRUD Endpoints for Settlement ---

@router.post(
    "/", 
    response_model=SettlementResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new settlement record"
)
def create_settlement(settlement: SettlementCreate, db: Session = Depends(get_db)):
    """
    Creates a new financial settlement record in the database.
    The initial status is typically PENDING.
    """
    logger.info(f"Attempting to create new settlement: {settlement.external_reference_id}")
    
    # Check for existing external reference ID to prevent duplicates
    if settlement.external_reference_id:
        existing_settlement = db.query(Settlement).filter(
            Settlement.external_reference_id == settlement.external_reference_id
        ).first()
        if existing_settlement:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Settlement with external_reference_id '{settlement.external_reference_id}' already exists (ID: {existing_settlement.id})"
            )

    db_settlement = Settlement(
        **settlement.model_dump(exclude_unset=True, exclude={"status"}),
        status=settlement.status.value
    )
    db.add(db_settlement)
    
    # Add initial log entry
    initial_log = SettlementLogCreate(
        level=LogLevel.INFO,
        message=f"Settlement created with status: {settlement.status.value}",
        details=f"Amount: {settlement.amount}, Currency: {settlement.currency}"
    )
    create_log_entry_internal(db, db_settlement.id, initial_log)
    
    db.refresh(db_settlement)
    logger.info(f"Settlement created successfully with ID: {db_settlement.id}")
    return db_settlement

@router.get(
    "/{settlement_id}", 
    response_model=SettlementResponse,
    summary="Retrieve a settlement by ID"
)
def read_settlement(settlement_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single settlement record, including its activity logs.
    """
    return get_settlement_by_id(db, settlement_id)

@router.get(
    "/", 
    response_model=List[SettlementResponse],
    summary="List all settlements with optional filtering and pagination"
)
def list_settlements(
    status_filter: Optional[SettlementStatus] = Query(None, description="Filter by settlement status"),
    currency_filter: Optional[str] = Query(None, description="Filter by currency code (e.g., USD)"),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """
    Returns a list of settlement records. Supports filtering by status and currency, 
    and includes pagination parameters.
    """
    query = db.query(Settlement)
    
    if status_filter:
        query = query.filter(Settlement.status == status_filter.value)
    
    if currency_filter:
        query = query.filter(func.lower(Settlement.currency) == currency_filter.lower())
        
    settlements = query.offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(settlements)} settlements (skip={skip}, limit={limit}, status={status_filter})")
    return settlements

@router.put(
    "/{settlement_id}", 
    response_model=SettlementResponse,
    summary="Update an existing settlement record"
)
def update_settlement(
    settlement_id: int, 
    settlement_update: SettlementUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates one or more fields of an existing settlement record.
    """
    db_settlement = get_settlement_by_id(db, settlement_id)
    
    update_data = settlement_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    for key, value in update_data.items():
        if key == "status":
            # Handle enum conversion for status
            setattr(db_settlement, key, value.value)
            # Log status change
            log_data = SettlementLogCreate(
                level=LogLevel.INFO,
                message=f"Status updated to: {value.value}",
                details=f"Updated by API call."
            )
            create_log_entry_internal(db, settlement_id, log_data)
        else:
            setattr(db_settlement, key, value)

    db.commit()
    db.refresh(db_settlement)
    logger.info(f"Settlement ID {settlement_id} updated.")
    return db_settlement

@router.delete(
    "/{settlement_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a settlement record"
)
def delete_settlement(settlement_id: int, db: Session = Depends(get_db)):
    """
    Deletes a settlement record and all associated logs.
    """
    db_settlement = get_settlement_by_id(db, settlement_id)
    
    db.delete(db_settlement)
    db.commit()
    logger.info(f"Settlement ID {settlement_id} and associated logs deleted.")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{settlement_id}/process",
    response_model=SettlementResponse,
    summary="Initiate the processing of a PENDING settlement"
)
def process_settlement(settlement_id: int, db: Session = Depends(get_db)):
    """
    Changes the status of a settlement from PENDING to PROCESSING.
    This initiates the financial transfer process via the configured payment gateway.
    """
    db_settlement = get_settlement_by_id(db, settlement_id)
    
    if db_settlement.status != SettlementStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Settlement is not PENDING. Current status: {db_settlement.status}. Only PENDING settlements can be processed."
        )
        
    new_status = SettlementStatus.PROCESSING.value
    db_settlement.status = new_status
    
    # Log the status change
    log_data = SettlementLogCreate(
        level=LogLevel.INFO,
        message=f"Settlement processing initiated. Status changed to {new_status}.",
        details=f"Transaction count: {db_settlement.transaction_count}"
    )
    create_log_entry_internal(db, settlement_id, log_data)
    
    db.commit()
    db.refresh(db_settlement)
    logger.info(f"Settlement ID {settlement_id} status changed to PROCESSING.")
    return db_settlement

@router.post(
    "/{settlement_id}/log",
    response_model=SettlementLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a manual activity log entry to a settlement"
)
def create_log_entry(
    settlement_id: int, 
    log_data: SettlementLogCreate, 
    db: Session = Depends(get_db)
):
    """
    Allows for the manual addition of an activity log entry to a specific settlement.
    Useful for external system updates or manual interventions.
    """
    # Ensure the settlement exists
    get_settlement_by_id(db, settlement_id)
    
    db_log = create_log_entry_internal(db, settlement_id, log_data)
    
    logger.info(f"Log entry created for Settlement ID {settlement_id}: {log_data.message}")
    return db_log

# --- Endpoint for creating database tables (for development/testing) ---

@router.post(
    "/initialize-db",
    status_code=status.HTTP_200_OK,
    summary="Initialize database tables (Development/Testing only)"
)
def initialize_database(db: Session = Depends(get_db)):
    """
    Creates all necessary database tables based on the SQLAlchemy models.
    NOTE: This should only be used for initial setup or testing.
    """
    try:
        # Import engine from config.py
        from .config import engine
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
        return {"message": "Database tables created successfully."}
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database initialization failed: {e}"
        )

# --- Example of how to use the router in a main application file (not part of the deliverable) ---
# from fastapi import FastAPI
# app = FastAPI()
# app.include_router(router)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
