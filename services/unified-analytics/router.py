import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from .config import get_db
from .models import (
    AnalyticsEvent,
    AnalyticsEventCreate,
    AnalyticsEventFullResponse,
    AnalyticsEventResponse,
    AnalyticsEventUpdate,
    ActivityLog,
    Base,
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/events",
    tags=["unified-analytics"],
    responses={404: {"description": "Not found"}},
)

# Helper function to create tables (for initial setup/testing)
def create_tables(db: Session):
    """Creates all defined tables in the database."""
    Base.metadata.create_all(bind=db.connection().engine)

# --- CRUD Operations for AnalyticsEvent ---

@router.post(
    "/",
    response_model=AnalyticsEventResponse,
    status_code=201,
    summary="Create a new analytics event",
    description="Records a new analytics event (e.g., page view, click, custom action) in the database.",
)
def create_event(event: AnalyticsEventCreate, db: Session = Depends(get_db)):
    """
    Creates a new AnalyticsEvent record and an associated ActivityLog entry.
    """
    logger.info(f"Attempting to create new event: {event.event_name}")
    
    # 1. Create the AnalyticsEvent object
    db_event = AnalyticsEvent(**event.model_dump(exclude_unset=True))
    db.add(db_event)
    db.flush() # Flush to get the ID for the log

    # 2. Create an ActivityLog entry
    db_log = ActivityLog(
        event_id=db_event.id,
        action="event_created",
        details=f"Event '{db_event.event_name}' recorded successfully.",
    )
    db.add(db_log)
    
    db.commit()
    db.refresh(db_event)
    logger.info(f"Event created successfully with ID: {db_event.id}")
    return db_event

@router.get(
    "/{event_id}",
    response_model=AnalyticsEventFullResponse,
    summary="Retrieve a single analytics event by ID",
    description="Fetches a specific analytics event and its associated activity logs.",
)
def read_event(event_id: UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single AnalyticsEvent by its UUID.
    Raises 404 if the event is not found.
    """
    logger.info(f"Attempting to read event with ID: {event_id}")
    db_event = db.query(AnalyticsEvent).filter(AnalyticsEvent.id == event_id).first()
    
    if db_event is None:
        logger.warning(f"Event not found: {event_id}")
        raise HTTPException(status_code=404, detail="Analytics Event not found")
    
    return db_event

@router.get(
    "/",
    response_model=List[AnalyticsEventResponse],
    summary="List all analytics events",
    description="Retrieves a list of analytics events with optional filtering and pagination.",
)
def list_events(
    event_name: Optional[str] = Query(None, description="Filter by event name"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip (offset)"),
    limit: int = Query(100, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """
    Lists AnalyticsEvents based on filters, with pagination.
    """
    logger.info(f"Listing events with skip={skip}, limit={limit}, filters: name={event_name}, user={user_id}")
    query = db.query(AnalyticsEvent)
    
    if event_name:
        query = query.filter(AnalyticsEvent.event_name == event_name)
    if user_id:
        query = query.filter(AnalyticsEvent.user_id == user_id)
        
    events = query.offset(skip).limit(limit).all()
    return events

@router.put(
    "/{event_id}",
    response_model=AnalyticsEventResponse,
    summary="Update an existing analytics event",
    description="Updates the details of an existing analytics event.",
)
def update_event(event_id: UUID, event: AnalyticsEventUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing AnalyticsEvent by its UUID.
    Raises 404 if the event is not found.
    """
    logger.info(f"Attempting to update event with ID: {event_id}")
    db_event = db.query(AnalyticsEvent).filter(AnalyticsEvent.id == event_id).first()
    
    if db_event is None:
        logger.warning(f"Update failed: Event not found: {event_id}")
        raise HTTPException(status_code=404, detail="Analytics Event not found")

    update_data = event.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_event, key, value)

    # Create an ActivityLog entry for the update
    db_log = ActivityLog(
        event_id=db_event.id,
        action="event_updated",
        details=f"Event fields updated: {list(update_data.keys())}",
    )
    db.add(db_log)
    
    db.commit()
    db.refresh(db_event)
    logger.info(f"Event updated successfully: {db_event.id}")
    return db_event

@router.delete(
    "/{event_id}",
    status_code=204,
    summary="Delete an analytics event",
    description="Deletes a specific analytics event and all its associated activity logs.",
)
def delete_event(event_id: UUID, db: Session = Depends(get_db)):
    """
    Deletes an AnalyticsEvent by its UUID.
    Raises 404 if the event is not found.
    """
    logger.info(f"Attempting to delete event with ID: {event_id}")
    db_event = db.query(AnalyticsEvent).filter(AnalyticsEvent.id == event_id).first()
    
    if db_event is None:
        logger.warning(f"Deletion failed: Event not found: {event_id}")
        raise HTTPException(status_code=404, detail="Analytics Event not found")
        
    db.delete(db_event)
    db.commit()
    logger.info(f"Event deleted successfully: {event_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.get(
    "/report/summary",
    summary="Get a summary report of analytics events",
    description="Provides a count of events, unique users, and a breakdown by event name.",
)
def get_summary_report(db: Session = Depends(get_db)):
    """
    Calculates and returns a high-level summary of the analytics data.
    """
    logger.info("Generating summary report.")
    
    total_events = db.query(AnalyticsEvent).count()
    
    unique_users_count = db.query(AnalyticsEvent.user_id).filter(AnalyticsEvent.user_id.isnot(None)).distinct().count()
    
    event_breakdown = (
        db.query(AnalyticsEvent.event_name, func.count(AnalyticsEvent.id))
        .group_by(AnalyticsEvent.event_name)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .all()
    )
    
    breakdown_dict = {name: count for name, count in event_breakdown}
    
    report = {
        "total_events": total_events,
        "unique_users_count": unique_users_count,
        "event_breakdown": breakdown_dict,
    }
    
    logger.info("Summary report generated.")
    return report

@router.get(
    "/report/user/{user_id}",
    response_model=List[AnalyticsEventResponse],
    summary="Get all events for a specific user",
    description="Retrieves all analytics events associated with a given user ID, ordered by creation time.",
)
def get_user_events(user_id: str, db: Session = Depends(get_db)):
    """
    Retrieves all events for a specific user ID.
    """
    logger.info(f"Retrieving events for user: {user_id}")
    user_events = (
        db.query(AnalyticsEvent)
        .filter(AnalyticsEvent.user_id == user_id)
        .order_by(AnalyticsEvent.created_at.desc())
        .all()
    )
    
    if not user_events:
        logger.info(f"No events found for user: {user_id}")
        # Return an empty list instead of 404, as a user with no events is a valid state
        return []
        
    return user_events
