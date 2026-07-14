import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from . import models
from .config import get_db, settings

# --- Setup Logging ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(settings.SERVICE_NAME)

# --- Router Initialization ---
router = APIRouter(
    prefix="/events",
    tags=["Communication Events"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def create_activity_log(db: Session, event_id: uuid.UUID, activity_type: str, details: str = None):
    """Creates a new activity log entry for a communication event."""
    log = models.CommunicationActivityLog(
        event_id=event_id,
        activity_type=activity_type,
        details=details
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.CommunicationEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new communication event",
    description="Creates a new record for a communication event (e.g., chat message, call log). An activity log for creation is automatically generated."
)
def create_event(event: models.CommunicationEventCreate, db: Session = Depends(get_db)):
    """
    Creates a new communication event in the database.
    """
    logger.info(f"Attempting to create new event of type: {event.event_type}")
    
    db_event = models.CommunicationEvent(**event.model_dump())
    
    try:
        db.add(db_event)
        db.flush() # Flush to get the ID for the log
        
        # Create initial activity log
        create_activity_log(
            db=db,
            event_id=db_event.id,
            activity_type="EVENT_CREATED",
            details=f"Event of type {db_event.event_type} created with status {db_event.status}"
        )
        
        db.commit()
        db.refresh(db_event)
        logger.info(f"Successfully created event with ID: {db_event.id}")
        return db_event
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the event: {e}"
        )

@router.get(
    "/{event_id}",
    response_model=models.CommunicationEventResponse,
    summary="Retrieve a communication event by ID",
    description="Fetches the details of a specific communication event, including its activity logs."
)
def read_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single communication event by its unique ID.
    """
    logger.info(f"Attempting to retrieve event with ID: {event_id}")
    
    db_event = db.get(models.CommunicationEvent, event_id)
    
    if db_event is None:
        logger.warning(f"Event not found with ID: {event_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication event with ID {event_id} not found"
        )
    
    return db_event

@router.get(
    "/",
    response_model=List[models.CommunicationEventResponse],
    summary="List all communication events",
    description="Retrieves a list of all communication events, with optional pagination and filtering for non-archived events."
)
def list_events(
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
    db: Session = Depends(get_db)
):
    """
    Lists communication events with pagination and an option to include archived events.
    """
    logger.info(f"Listing events: skip={skip}, limit={limit}, include_archived={include_archived}")
    
    stmt = select(models.CommunicationEvent).offset(skip).limit(limit).order_by(models.CommunicationEvent.timestamp.desc())
    
    if not include_archived:
        stmt = stmt.where(models.CommunicationEvent.is_archived == False)
        
    events = db.scalars(stmt).all()
    
    return events

@router.put(
    "/{event_id}",
    response_model=models.CommunicationEventResponse,
    summary="Update an existing communication event",
    description="Updates the details of an existing communication event. An activity log is created for the update."
)
def update_event(event_id: uuid.UUID, event_update: models.CommunicationEventUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing communication event by its ID.
    """
    logger.info(f"Attempting to update event with ID: {event_id}")
    
    db_event = db.get(models.CommunicationEvent, event_id)
    
    if db_event is None:
        logger.warning(f"Update failed: Event not found with ID: {event_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication event with ID {event_id} not found"
        )

    update_data = event_update.model_dump(exclude_unset=True)
    
    if not update_data:
        logger.info(f"No data provided for update of event ID: {event_id}")
        return db_event # Return the existing object if no changes were requested

    # Apply updates
    for key, value in update_data.items():
        setattr(db_event, key, value)
        
    try:
        # Create activity log for the update
        create_activity_log(
            db=db,
            event_id=db_event.id,
            activity_type="EVENT_UPDATED",
            details=f"Fields updated: {', '.join(update_data.keys())}"
        )
        
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        logger.info(f"Successfully updated event with ID: {event_id}")
        return db_event
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating event {event_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the event: {e}"
        )

@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive (Soft Delete) a communication event",
    description="Archives a communication event by setting the 'is_archived' flag to True. This is a soft delete operation."
)
def archive_event(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Archives a communication event by setting `is_archived` to True.
    """
    logger.info(f"Attempting to archive event with ID: {event_id}")
    
    # Check if event exists and is not already archived
    db_event = db.get(models.CommunicationEvent, event_id)
    
    if db_event is None:
        logger.warning(f"Archive failed: Event not found with ID: {event_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication event with ID {event_id} not found"
        )
        
    if db_event.is_archived:
        logger.info(f"Event ID {event_id} is already archived.")
        return # Already archived, return 204 No Content

    try:
        # Perform the soft delete (archive)
        db_event.is_archived = True
        
        # Create activity log for archiving
        create_activity_log(
            db=db,
            event_id=db_event.id,
            activity_type="EVENT_ARCHIVED",
            details="Communication event has been soft-deleted (archived)."
        )
        
        db.add(db_event)
        db.commit()
        logger.info(f"Successfully archived event with ID: {event_id}")
        return
    except Exception as e:
        db.rollback()
        logger.error(f"Error archiving event {event_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while archiving the event: {e}"
        )

# --- Business-Specific Endpoints ---

@router.get(
    "/user/{user_id}",
    response_model=List[models.CommunicationEventResponse],
    summary="List communication events for a specific user",
    description="Retrieves all communication events where the specified user is either the sender or the recipient."
)
def list_events_for_user(
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lists communication events where the user is either the sender or recipient.
    """
    logger.info(f"Listing events for user ID: {user_id}")
    
    stmt = (
        select(models.CommunicationEvent)
        .where(
            (models.CommunicationEvent.sender_id == user_id) | 
            (models.CommunicationEvent.recipient_id == user_id)
        )
        .where(models.CommunicationEvent.is_archived == False)
        .offset(skip)
        .limit(limit)
        .order_by(models.CommunicationEvent.timestamp.desc())
    )
    
    events = db.scalars(stmt).all()
    
    return events

@router.get(
    "/{event_id}/logs",
    response_model=List[models.CommunicationActivityLogResponse],
    summary="Retrieve activity logs for an event",
    description="Fetches the historical activity logs for a specific communication event."
)
def get_event_logs(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves all activity logs associated with a given communication event ID.
    """
    logger.info(f"Retrieving logs for event ID: {event_id}")
    
    # Check if the event exists first
    if not db.get(models.CommunicationEvent, event_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication event with ID {event_id} not found"
        )
        
    stmt = (
        select(models.CommunicationActivityLog)
        .where(models.CommunicationActivityLog.event_id == event_id)
        .order_by(models.CommunicationActivityLog.created_at.asc())
    )
    
    logs = db.scalars(stmt).all()
    
    return logs
