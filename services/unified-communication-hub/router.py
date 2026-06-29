from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from . import models
from .config import get_db, logger
from .models import (
    CommunicationEvent,
    CommunicationEventCreate,
    CommunicationEventResponse,
    CommunicationEventUpdate,
    EventStatus,
    ActivityLog,
    LogAction,
)

router = APIRouter(
    prefix="/events",
    tags=["communication-events"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def _log_activity(db: Session, event_id: int, action: LogAction, user_id: int, details: Optional[str] = None):
    """
    Helper function to create an activity log entry.
    """
    log_entry = models.ActivityLog(
        event_id=event_id,
        action=action,
        user_id=user_id,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# --- CRUD Endpoints for CommunicationEvent ---

@router.post(
    "/",
    response_model=CommunicationEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new communication event",
    description="Creates a new communication event (e.g., a message, call log, or notification)."
)
def create_event(event: CommunicationEventCreate, db: Session = Depends(get_db)):
    """
    Creates a new communication event in the database.
    """
    db_event = CommunicationEvent(**event.model_dump())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Log the creation activity
    _log_activity(db, db_event.id, LogAction.CREATE, db_event.sender_id, "Event created")
    
    logger.info(f"Created event ID: {db_event.id} from sender: {db_event.sender_id}")
    return db_event

@router.get(
    "/{event_id}",
    response_model=CommunicationEventResponse,
    summary="Retrieve a specific communication event",
    description="Fetches a communication event by its unique ID."
)
def read_event(event_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a communication event by ID.
    """
    db_event = db.query(CommunicationEvent).filter(CommunicationEvent.id == event_id).first()
    if db_event is None:
        logger.warning(f"Attempted to read non-existent event ID: {event_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication Event not found")
    return db_event

@router.get(
    "/",
    response_model=List[CommunicationEventResponse],
    summary="List all communication events",
    description="Retrieves a list of all communication events with optional filtering and pagination."
)
def list_events(
    skip: int = 0,
    limit: int = 100,
    sender_id: Optional[int] = None,
    recipient_id: Optional[int] = None,
    status_filter: Optional[EventStatus] = None,
    db: Session = Depends(get_db)
):
    """
    Lists communication events with optional filters.
    """
    query = db.query(CommunicationEvent)
    
    if sender_id is not None:
        query = query.filter(CommunicationEvent.sender_id == sender_id)
    
    if recipient_id is not None:
        query = query.filter(CommunicationEvent.recipient_id == recipient_id)
        
    if status_filter is not None:
        query = query.filter(CommunicationEvent.status == status_filter)
        
    events = query.offset(skip).limit(limit).all()
    return events

@router.put(
    "/{event_id}",
    response_model=CommunicationEventResponse,
    summary="Update an existing communication event",
    description="Updates the content or status of a communication event."
)
def update_event(
    event_id: int,
    event_update: CommunicationEventUpdate,
    user_id: int = Field(..., description="The ID of the user performing the update (for logging)."),
    db: Session = Depends(get_db)
):
    """
    Updates an existing communication event.
    """
    db_event = db.query(CommunicationEvent).filter(CommunicationEvent.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication Event not found")

    update_data = event_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    # Check for status change to log it specifically
    old_status = db_event.status
    new_status = update_data.get("status")
    
    for key, value in update_data.items():
        setattr(db_event, key, value)

    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Log the update activity
    details = f"Event updated. Content changed: {'content' in update_data}. Status changed: {old_status} -> {new_status}"
    _log_activity(db, db_event.id, LogAction.UPDATE, user_id, details)
    
    logger.info(f"Updated event ID: {db_event.id}")
    return db_event

@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a communication event",
    description="Deletes a communication event by its unique ID."
)
def delete_event(
    event_id: int,
    user_id: int = Field(..., description="The ID of the user performing the deletion (for logging)."),
    db: Session = Depends(get_db)
):
    """
    Deletes a communication event.
    """
    db_event = db.query(CommunicationEvent).filter(CommunicationEvent.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication Event not found")

    # Log the deletion activity before deleting the event (which will cascade delete logs)
    # Note: In a real system, you might want to log this to a separate, non-cascading table.
    # For this exercise, we log it to the ActivityLog which will be deleted with the event.
    _log_activity(db, db_event.id, LogAction.DELETE, user_id, "Event deleted")
    
    db.delete(db_event)
    db.commit()
    
    logger.info(f"Deleted event ID: {event_id}")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{event_id}/read",
    response_model=CommunicationEventResponse,
    summary="Mark a communication event as read",
    description="Sets the status of a communication event to 'read'."
)
def mark_event_as_read(
    event_id: int,
    user_id: int = Field(..., description="The ID of the user who read the event."),
    db: Session = Depends(get_db)
):
    """
    Marks a specific event as read and logs the action.
    """
    db_event = db.query(CommunicationEvent).filter(CommunicationEvent.id == event_id).first()
    if db_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication Event not found")

    if db_event.status == EventStatus.READ:
        return db_event # Already read, no change needed

    # Update status
    db_event.status = EventStatus.READ
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    # Log the status change
    _log_activity(db, db_event.id, LogAction.STATUS_CHANGE, user_id, f"Status changed to {EventStatus.READ}")
    
    logger.info(f"Event ID: {event_id} marked as read by user: {user_id}")
    return db_event

@router.get(
    "/user/{user_id}/history",
    response_model=List[CommunicationEventResponse],
    summary="Get a user's communication history",
    description="Retrieves all communication events where the user is either the sender or the recipient."
)
def get_user_history(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Fetches the communication history for a given user ID.
    """
    history = (
        db.query(CommunicationEvent)
        .filter(
            or_(
                CommunicationEvent.sender_id == user_id,
                CommunicationEvent.recipient_id == user_id
            )
        )
        .order_by(CommunicationEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    logger.info(f"Retrieved {len(history)} events for user ID: {user_id}")
    return history
