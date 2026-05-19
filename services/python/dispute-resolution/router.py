import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

# Assuming config.py and models.py are in the same directory or importable path
from config import get_db, get_settings
from models import (
    Base,
    Dispute,
    DisputeActivityLog,
    DisputeCreate,
    DisputeResponse,
    DisputeStatus,
    DisputeStatusUpdate,
    DisputeUpdate,
    ActivityType,
)

# --- Configuration and Logging ---

settings = get_settings()
# Basic logging configuration
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.SERVICE_NAME)

# --- Router Setup ---

router = APIRouter(
    prefix="/disputes",
    tags=["disputes"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def create_activity_log(
    db: Session, 
    dispute_id: uuid.UUID, 
    activity_type: ActivityType, 
    actor_id: int, 
    details: Optional[str] = None
) -> DisputeActivityLog:
    """Creates and adds an activity log entry to the database."""
    log_entry = DisputeActivityLog(
        dispute_id=dispute_id,
        activity_type=activity_type,
        actor_id=actor_id,
        details=details,
    )
    db.add(log_entry)
    # Note: The log entry will be committed with the main transaction
    return log_entry

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=DisputeResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new dispute",
    description="Submits a new dispute for resolution. Automatically logs the creation activity."
)
def create_dispute(dispute_in: DisputeCreate, db: Session = Depends(get_db)):
    """
    Creates a new dispute record in the database.
    """
    logger.info(f"Attempting to create new dispute for submitter_id: {dispute_in.submitter_id}")
    
    # 1. Create the Dispute object
    db_dispute = Dispute(**dispute_in.model_dump())
    
    # 2. Add initial activity log
    create_activity_log(
        db=db,
        dispute_id=db_dispute.id,
        activity_type=ActivityType.CREATED,
        actor_id=dispute_in.submitter_id,
        details=f"Dispute created by user {dispute_in.submitter_id}",
    )
    
    # 3. Commit to database
    db.add(db_dispute)
    db.commit()
    db.refresh(db_dispute)
    
    logger.info(f"Dispute created successfully with ID: {db_dispute.id}")
    return db_dispute

@router.get(
    "/{dispute_id}", 
    response_model=DisputeResponse,
    summary="Get a dispute by ID",
    description="Retrieves the details of a specific dispute, including its activity log."
)
def read_dispute(dispute_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a dispute by its unique ID.
    """
    logger.debug(f"Fetching dispute with ID: {dispute_id}")
    
    db_dispute = db.query(Dispute).options(joinedload(Dispute.activity_log)).filter(Dispute.id == dispute_id).first()
    
    if db_dispute is None:
        logger.warning(f"Dispute not found with ID: {dispute_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Dispute with ID {dispute_id} not found"
        )
    
    return db_dispute

@router.get(
    "/", 
    response_model=List[DisputeResponse],
    summary="List all disputes",
    description="Retrieves a list of disputes with optional filtering and pagination."
)
def list_disputes(
    status_filter: Optional[DisputeStatus] = Query(None, description="Filter by dispute status"),
    submitter_id: Optional[int] = Query(None, description="Filter by the ID of the user who submitted the dispute"),
    skip: int = Query(0, ge=0, description="Number of records to skip (for pagination)"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """
    Lists disputes, supporting filtering by status and submitter_id, and pagination.
    """
    logger.debug(f"Listing disputes with filters: status={status_filter}, submitter={submitter_id}, skip={skip}, limit={limit}")
    
    query = db.query(Dispute).options(joinedload(Dispute.activity_log))
    
    if status_filter:
        query = query.filter(Dispute.status == status_filter)
    
    if submitter_id:
        query = query.filter(Dispute.submitter_id == submitter_id)
        
    disputes = query.offset(skip).limit(limit).all()
    
    return disputes

@router.put(
    "/{dispute_id}", 
    response_model=DisputeResponse,
    summary="Update an existing dispute",
    description="Updates the details of an existing dispute. Automatically logs the update activity."
)
def update_dispute(
    dispute_id: uuid.UUID, 
    dispute_in: DisputeUpdate, 
    actor_id: int = Query(..., description="ID of the user performing the update"),
    db: Session = Depends(get_db)
):
    """
    Updates an existing dispute record.
    """
    logger.info(f"Attempting to update dispute with ID: {dispute_id} by actor: {actor_id}")
    
    db_dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    
    if db_dispute is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Dispute with ID {dispute_id} not found"
        )

    update_data = dispute_in.model_dump(exclude_unset=True)
    
    # Check if status is being updated
    status_changed = "status" in update_data and update_data["status"] != db_dispute.status
    
    # Apply updates
    for key, value in update_data.items():
        setattr(db_dispute, key, value)
        
    # Handle resolution time if status changes to RESOLVED or CLOSED
    if status_changed:
        if db_dispute.status in [DisputeStatus.RESOLVED, DisputeStatus.CLOSED]:
            db_dispute.resolved_at = datetime.utcnow()
        else:
            db_dispute.resolved_at = None
            
        # Log status change
        create_activity_log(
            db=db,
            dispute_id=db_dispute.id,
            activity_type=ActivityType.STATUS_UPDATE,
            actor_id=actor_id,
            details=f"Status changed to {db_dispute.status.value}",
        )
    
    # Log general update if other fields were changed
    if len(update_data) > 0 and not status_changed:
        create_activity_log(
            db=db,
            dispute_id=db_dispute.id,
            activity_type=ActivityType.COMMENT, # Using COMMENT for general updates for simplicity
            actor_id=actor_id,
            details=f"Dispute details updated by user {actor_id}",
        )

    db.add(db_dispute)
    db.commit()
    db.refresh(db_dispute)
    
    logger.info(f"Dispute {dispute_id} updated successfully.")
    return db_dispute

@router.delete(
    "/{dispute_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dispute",
    description="Deletes a dispute and all associated activity logs. This action is irreversible."
)
def delete_dispute(dispute_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes a dispute by its unique ID.
    """
    logger.warning(f"Attempting to delete dispute with ID: {dispute_id}")
    
    db_dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    
    if db_dispute is None:
        # Return 204 even if not found, as the end state (deleted) is achieved (Idempotency)
        return
    
    db.delete(db_dispute)
    db.commit()
    
    logger.info(f"Dispute {dispute_id} deleted successfully.")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{dispute_id}/status",
    response_model=DisputeResponse,
    summary="Update dispute status",
    description="Updates only the status of a dispute and logs the change."
)
def update_dispute_status(
    dispute_id: uuid.UUID,
    status_update: DisputeStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates the status of a dispute and logs the activity.
    """
    logger.info(f"Updating status for dispute {dispute_id} to {status_update.status.value}")
    
    db_dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    
    if db_dispute is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Dispute with ID {dispute_id} not found"
        )
        
    if db_dispute.status == status_update.status:
        logger.info(f"Status for dispute {dispute_id} is already {status_update.status.value}. No change applied.")
        return db_dispute

    # Update status
    db_dispute.status = status_update.status
    
    # Handle resolution time
    if db_dispute.status in [DisputeStatus.RESOLVED, DisputeStatus.CLOSED]:
        db_dispute.resolved_at = datetime.utcnow()
    else:
        db_dispute.resolved_at = None
        
    # Log status change
    create_activity_log(
        db=db,
        dispute_id=db_dispute.id,
        activity_type=ActivityType.STATUS_UPDATE,
        actor_id=status_update.actor_id,
        details=status_update.details or f"Status changed to {status_update.status.value}",
    )
    
    db.add(db_dispute)
    db.commit()
    db.refresh(db_dispute)
    
    logger.info(f"Dispute {dispute_id} status updated to {db_dispute.status.value}.")
    return db_dispute

@router.post(
    "/{dispute_id}/assign/{assigned_to_id}",
    response_model=DisputeResponse,
    summary="Assign dispute to a user",
    description="Assigns the dispute to a specific user ID for handling."
)
def assign_dispute(
    dispute_id: uuid.UUID,
    assigned_to_id: int,
    actor_id: int = Query(..., description="ID of the user performing the assignment"),
    db: Session = Depends(get_db)
):
    """
    Assigns a dispute to a specific user.
    """
    logger.info(f"Assigning dispute {dispute_id} to user {assigned_to_id}")
    
    db_dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    
    if db_dispute is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Dispute with ID {dispute_id} not found"
        )
        
    if db_dispute.assigned_to_id == assigned_to_id:
        logger.info(f"Dispute {dispute_id} is already assigned to user {assigned_to_id}. No change applied.")
        return db_dispute

    # Update assignment
    db_dispute.assigned_to_id = assigned_to_id
    
    # Log assignment
    create_activity_log(
        db=db,
        dispute_id=db_dispute.id,
        activity_type=ActivityType.ASSIGNED,
        actor_id=actor_id,
        details=f"Dispute assigned to user {assigned_to_id}",
    )
    
    db.add(db_dispute)
    db.commit()
    db.refresh(db_dispute)
    
    logger.info(f"Dispute {dispute_id} assigned to user {assigned_to_id}.")
    return db_dispute

@router.post(
    "/{dispute_id}/comment",
    response_model=DisputeResponse,
    summary="Add a comment/activity to a dispute",
    description="Adds a general comment or activity log entry to the dispute."
)
def add_dispute_comment(
    dispute_id: uuid.UUID,
    comment: str = Query(..., description="The comment or activity detail to add"),
    actor_id: int = Query(..., description="ID of the user adding the comment"),
    db: Session = Depends(get_db)
):
    """
    Adds a comment/activity log entry to a dispute.
    """
    logger.info(f"Adding comment to dispute {dispute_id} by actor {actor_id}")
    
    db_dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    
    if db_dispute is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Dispute with ID {dispute_id} not found"
        )
        
    # Log comment
    create_activity_log(
        db=db,
        dispute_id=db_dispute.id,
        activity_type=ActivityType.COMMENT,
        actor_id=actor_id,
        details=comment,
    )
    
    db.commit()
    db.refresh(db_dispute)
    
    logger.info(f"Comment added to dispute {dispute_id}.")
    return db_dispute

# --- Initialization (Optional but helpful for testing) ---

@router.post(
    "/initialize_db",
    status_code=status.HTTP_200_OK,
    summary="Initialize Database",
    description="Creates all necessary tables in the database. Use with caution in production."
)
def initialize_db(db: Session = Depends(get_db)):
    """
    Initializes the database by creating all tables defined in Base.
    """
    try:
        Base.metadata.create_all(bind=db.get_bind())
        logger.info("Database tables created successfully.")
        return {"message": "Database tables created successfully."}
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database initialization failed: {e}"
        )
