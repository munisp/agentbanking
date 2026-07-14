import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/voice-assistant",
    tags=["Voice Assistant Sessions"],
)

# --- Session Endpoints ---

@router.post(
    "/sessions",
    response_model=models.VoiceAssistantSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new voice assistant session",
    description="Creates a new voice assistant session record in the database."
)
def start_session(
    session_data: models.VoiceAssistantSessionCreate,
    db: Session = Depends(config.get_db)
):
    """
    Creates a new voice assistant session.

    Args:
        session_data: The data required to create a new session.
        db: The database session dependency.

    Returns:
        The newly created session object.
    """
    db_session = models.VoiceAssistantSession(**session_data.model_dump())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    logger.info(f"Session started: ID {db_session.id}, User {db_session.user_id}")
    return db_session

@router.get(
    "/sessions/{session_id}",
    response_model=models.VoiceAssistantSessionWithActivities,
    summary="Get a specific session and its activities",
    description="Retrieves a voice assistant session by its ID, including all associated activity logs."
)
def get_session(
    session_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Retrieves a voice assistant session by ID.

    Args:
        session_id: The ID of the session to retrieve.
        db: The database session dependency.

    Returns:
        The session object with its activities.
    
    Raises:
        HTTPException 404: If the session is not found.
    """
    db_session = db.query(models.VoiceAssistantSession).filter(models.VoiceAssistantSession.id == session_id).first()
    if db_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return db_session

@router.get(
    "/sessions",
    response_model=List[models.VoiceAssistantSessionResponse],
    summary="List all sessions",
    description="Retrieves a list of all voice assistant sessions, with optional filtering by user ID and status."
)
def list_sessions(
    user_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(config.get_db)
):
    """
    Lists voice assistant sessions with optional filtering and pagination.

    Args:
        user_id: Optional user ID to filter sessions.
        status_filter: Optional status to filter sessions (e.g., 'active', 'completed').
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return.
        db: The database session dependency.

    Returns:
        A list of session objects.
    """
    query = db.query(models.VoiceAssistantSession)
    if user_id is not None:
        query = query.filter(models.VoiceAssistantSession.user_id == user_id)
    if status_filter is not None:
        query = query.filter(models.VoiceAssistantSession.status == status_filter)
        
    sessions = query.offset(skip).limit(limit).all()
    return sessions

@router.put(
    "/sessions/{session_id}/end",
    response_model=models.VoiceAssistantSessionResponse,
    summary="End an active session",
    description="Updates the session status to 'completed' and sets the end_time to the current time."
)
def end_session(
    session_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Ends an active voice assistant session.

    Args:
        session_id: The ID of the session to end.
        db: The database session dependency.

    Returns:
        The updated session object.

    Raises:
        HTTPException 404: If the session is not found.
    """
    db_session = db.query(models.VoiceAssistantSession).filter(models.VoiceAssistantSession.id == session_id).first()
    if db_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if db_session.status != "completed":
        db_session.status = "completed"
        db_session.end_time = datetime.utcnow()
        db.commit()
        db.refresh(db_session)
        logger.info(f"Session ended: ID {db_session.id}")
    
    return db_session

@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
    description="Deletes a voice assistant session and all its associated activity logs."
)
def delete_session(
    session_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Deletes a voice assistant session and all related activities.

    Args:
        session_id: The ID of the session to delete.
        db: The database session dependency.

    Raises:
        HTTPException 404: If the session is not found.
    """
    db_session = db.query(models.VoiceAssistantSession).filter(models.VoiceAssistantSession.id == session_id).first()
    if db_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    db.delete(db_session)
    db.commit()
    logger.warning(f"Session deleted: ID {session_id}")
    return

# --- Activity Log Endpoints ---

@router.post(
    "/activities",
    response_model=models.ActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new activity",
    description="Adds a new activity log entry to an existing voice assistant session."
)
def log_activity(
    activity_data: models.ActivityLogCreate,
    db: Session = Depends(config.get_db)
):
    """
    Logs a new activity within a session.

    Args:
        activity_data: The data required to create a new activity log.
        db: The database session dependency.

    Returns:
        The newly created activity log object.

    Raises:
        HTTPException 404: If the associated session is not found.
    """
    # Check if session exists
    session = db.query(models.VoiceAssistantSession).filter(models.VoiceAssistantSession.id == activity_data.session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Session with ID {activity_data.session_id} not found")

    db_activity = models.ActivityLog(**activity_data.model_dump())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    logger.debug(f"Activity logged for Session {db_activity.session_id}: Type {db_activity.activity_type}")
    return db_activity

@router.get(
    "/sessions/{session_id}/activities",
    response_model=List[models.ActivityLogResponse],
    summary="List activities for a session",
    description="Retrieves all activity logs for a specific voice assistant session."
)
def list_session_activities(
    session_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(config.get_db)
):
    """
    Lists all activity logs for a given session ID.

    Args:
        session_id: The ID of the session.
        skip: Number of records to skip (for pagination).
        limit: Maximum number of records to return.
        db: The database session dependency.

    Returns:
        A list of activity log objects.
    """
    activities = db.query(models.ActivityLog).filter(models.ActivityLog.session_id == session_id).offset(skip).limit(limit).all()
    return activities
