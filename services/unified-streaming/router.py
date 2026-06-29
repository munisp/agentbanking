import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/streams",
    tags=["unified-streaming"],
    responses={404: {"description": "Not found"}},
)

def log_activity(db: Session, stream_id: int, action: str, details: str = None, user_id: str = "system"):
    """Helper function to log an activity for a stream."""
    log_entry = models.UnifiedStreamActivityLogCreate(
        stream_id=stream_id,
        action=action,
        details=details,
        user_id=user_id
    )
    db_log = models.UnifiedStreamActivityLog(**log_entry.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

# --- CRUD Operations for UnifiedStream ---

@router.post(
    "/",
    response_model=models.UnifiedStreamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new unified stream configuration",
)
def create_stream(stream: models.UnifiedStreamCreate, db: Session = Depends(get_db)):
    """
    Creates a new stream configuration in the database.

    Raises:
        HTTPException: 409 Conflict if a stream with the same name already exists.
    """
    logger.info(f"Attempting to create new stream: {stream.name}")
    db_stream = models.UnifiedStream(**stream.model_dump())
    try:
        db.add(db_stream)
        db.commit()
        db.refresh(db_stream)
        log_activity(db, db_stream.id, "created", f"Stream {db_stream.name} created successfully.")
        logger.info(f"Stream created successfully with ID: {db_stream.id}")
        return db_stream
    except IntegrityError:
        db.rollback()
        logger.warning(f"Creation failed: Stream with name '{stream.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stream with name '{stream.name}' already exists."
        )

@router.get(
    "/",
    response_model=List[models.UnifiedStreamResponse],
    summary="Retrieve a list of all unified stream configurations",
)
def list_streams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a paginated list of all stream configurations.
    """
    logger.info(f"Retrieving streams with skip={skip}, limit={limit}")
    streams = db.query(models.UnifiedStream).offset(skip).limit(limit).all()
    return streams

@router.get(
    "/{stream_id}",
    response_model=models.UnifiedStreamResponse,
    summary="Retrieve a specific unified stream configuration by ID",
)
def read_stream(stream_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single stream configuration by its unique ID.

    Raises:
        HTTPException: 404 Not Found if the stream does not exist.
    """
    logger.info(f"Retrieving stream with ID: {stream_id}")
    stream = db.query(models.UnifiedStream).filter(models.UnifiedStream.id == stream_id).first()
    if stream is None:
        logger.warning(f"Retrieval failed: Stream with ID {stream_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stream with ID {stream_id} not found"
        )
    return stream

@router.put(
    "/{stream_id}",
    response_model=models.UnifiedStreamResponse,
    summary="Update an existing unified stream configuration",
)
def update_stream(stream_id: int, stream_update: models.UnifiedStreamUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing stream configuration. Only provided fields are updated.

    Raises:
        HTTPException: 404 Not Found if the stream does not exist.
    """
    logger.info(f"Attempting to update stream with ID: {stream_id}")
    db_stream = read_stream(stream_id, db) # Reuses read_stream for 404 check

    update_data = stream_update.model_dump(exclude_unset=True)
    if not update_data:
        logger.info(f"No update data provided for stream ID: {stream_id}")
        return db_stream # Return existing object if no fields are provided

    for key, value in update_data.items():
        setattr(db_stream, key, value)

    try:
        db.add(db_stream)
        db.commit()
        db.refresh(db_stream)
        log_activity(db, db_stream.id, "updated", f"Stream updated with fields: {list(update_data.keys())}")
        logger.info(f"Stream ID {stream_id} updated successfully.")
        return db_stream
    except IntegrityError:
        db.rollback()
        logger.warning(f"Update failed: Integrity error for stream ID {stream_id}.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update failed due to a conflict (e.g., duplicate name)."
        )

@router.delete(
    "/{stream_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a unified stream configuration",
)
def delete_stream(stream_id: int, db: Session = Depends(get_db)):
    """
    Deletes a stream configuration and all associated activity logs.

    Raises:
        HTTPException: 404 Not Found if the stream does not exist.
    """
    logger.info(f"Attempting to delete stream with ID: {stream_id}")
    db_stream = read_stream(stream_id, db) # Reuses read_stream for 404 check

    db.delete(db_stream)
    db.commit()
    logger.info(f"Stream ID {stream_id} deleted successfully.")
    # Activity log is deleted via cascade, no need to log a separate activity

# --- Business-Specific Endpoint ---

@router.post(
    "/{stream_id}/activate",
    response_model=models.UnifiedStreamResponse,
    summary="Activate a unified stream",
    description="Sets the stream status to 'active' and logs the activation event.",
)
def activate_stream(stream_id: int, db: Session = Depends(get_db)):
    """
    Activates the specified stream by setting its status to 'active'.

    Raises:
        HTTPException: 404 Not Found if the stream does not exist.
        HTTPException: 400 Bad Request if the stream is already active.
    """
    logger.info(f"Attempting to activate stream with ID: {stream_id}")
    db_stream = read_stream(stream_id, db)

    if db_stream.status == "active":
        logger.warning(f"Activation failed: Stream ID {stream_id} is already active.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stream with ID {stream_id} is already active."
        )

    db_stream.status = "active"
    db.add(db_stream)
    db.commit()
    db.refresh(db_stream)
    log_activity(db, db_stream.id, "status_change", "Stream status changed to 'active'.")
    logger.info(f"Stream ID {stream_id} activated successfully.")
    return db_stream
