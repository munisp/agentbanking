import logging
from typing import List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models
from .config import get_db

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(
    prefix="/snaps",
    tags=["snaps"],
    responses={404: {"description": "Not found"}},
)

# Helper function to create an activity log
def create_activity_log(db: Session, snap_id: int, user_id: int, activity_type: str):
    """Creates a new entry in the SnapActivityLog table."""
    log_entry = models.SnapActivityLog(
        snap_id=snap_id,
        user_id=user_id,
        activity_type=activity_type
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# ----------------------------------------------------------------------
# CRUD Endpoints
# ----------------------------------------------------------------------

@router.post(
    "/", 
    response_model=models.SnapResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Snap",
    description="Creates a new Snap with an expiration time (24 hours from creation) and logs the creation activity."
)
def create_snap(snap: models.SnapCreate, db: Session = Depends(get_db)):
    """
    Creates a new Snap in the database.
    
    - **snap**: The SnapCreate schema containing snap details.
    - **db**: Database session dependency.
    - **Returns**: The created Snap object.
    """
    logger.info(f"Attempting to create snap for user_id: {snap.user_id}")
    
    # Calculate expiration time (e.g., 24 hours from now)
    expires_at = datetime.now() + timedelta(hours=24)
    
    db_snap = models.Snap(
        **snap.model_dump(),
        expires_at=expires_at
    )
    
    try:
        db.add(db_snap)
        db.commit()
        db.refresh(db_snap)
        
        # Log the creation activity
        create_activity_log(db, db_snap.id, db_snap.user_id, "CREATED")
        
        logger.info(f"Snap created successfully with ID: {db_snap.id}")
        return db_snap
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating snap: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the snap: {e}"
        )


@router.get(
    "/{snap_id}", 
    response_model=models.SnapResponse,
    summary="Get a Snap by ID",
    description="Retrieves a specific Snap by its ID, only if it has not expired."
)
def read_snap(snap_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single Snap by ID.
    
    - **snap_id**: The ID of the snap to retrieve.
    - **db**: Database session dependency.
    - **Returns**: The Snap object.
    - **Raises**: 404 if the snap is not found or has expired.
    """
    db_snap = db.query(models.Snap).filter(
        models.Snap.id == snap_id,
        models.Snap.expires_at > func.now()
    ).first()
    
    if db_snap is None:
        logger.warning(f"Snap with ID {snap_id} not found or expired.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Snap not found or has expired"
        )
    return db_snap


@router.get(
    "/", 
    response_model=List[models.SnapResponse],
    summary="List all active Snaps for a user",
    description="Retrieves a list of all active (non-expired) Snaps for a given user ID."
)
def list_snaps(user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a list of active Snaps for a user.
    
    - **user_id**: The ID of the user whose snaps to retrieve.
    - **skip**: Number of records to skip for pagination.
    - **limit**: Maximum number of records to return.
    - **db**: Database session dependency.
    - **Returns**: A list of Snap objects.
    """
    snaps = db.query(models.Snap).filter(
        models.Snap.user_id == user_id,
        models.Snap.expires_at > func.now()
    ).offset(skip).limit(limit).all()
    
    logger.info(f"Retrieved {len(snaps)} active snaps for user_id: {user_id}")
    return snaps


@router.put(
    "/{snap_id}", 
    response_model=models.SnapResponse,
    summary="Update a Snap",
    description="Updates the caption and/or duration of an existing Snap."
)
def update_snap(snap_id: int, snap_update: models.SnapUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing Snap.
    
    - **snap_id**: The ID of the snap to update.
    - **snap_update**: The SnapUpdate schema with fields to modify.
    - **db**: Database session dependency.
    - **Returns**: The updated Snap object.
    - **Raises**: 404 if the snap is not found.
    """
    db_snap = db.query(models.Snap).filter(models.Snap.id == snap_id).first()
    
    if db_snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Snap not found"
        )
    
    update_data = snap_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_snap, key, value)
        
    db.commit()
    db.refresh(db_snap)
    
    logger.info(f"Snap with ID {snap_id} updated.")
    return db_snap


@router.delete(
    "/{snap_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Snap",
    description="Deletes a Snap by its ID and logs the deletion activity."
)
def delete_snap(snap_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    Deletes a Snap from the database.
    
    - **snap_id**: The ID of the snap to delete.
    - **user_id**: The ID of the user performing the deletion (for logging/authorization).
    - **db**: Database session dependency.
    - **Raises**: 404 if the snap is not found.
    """
    db_snap = db.query(models.Snap).filter(models.Snap.id == snap_id).first()
    
    if db_snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Snap not found"
        )
        
    # Log the deletion activity before deleting the snap (CASCADE will handle logs)
    create_activity_log(db, db_snap.id, user_id, "DELETED")
    
    db.delete(db_snap)
    db.commit()
    
    logger.info(f"Snap with ID {snap_id} deleted.")
    return {"ok": True}

# ----------------------------------------------------------------------
# Business-Specific Endpoints
# ----------------------------------------------------------------------

@router.post(
    "/{snap_id}/view", 
    response_model=models.SnapResponse,
    summary="View a Snap",
    description="Marks a Snap as viewed and logs the viewing activity. This is the core business logic for a Snap."
)
def view_snap(snap_id: int, viewer_user_id: int, db: Session = Depends(get_db)):
    """
    Marks a Snap as viewed and logs the activity.
    
    - **snap_id**: The ID of the snap being viewed.
    - **viewer_user_id**: The ID of the user viewing the snap.
    - **db**: Database session dependency.
    - **Returns**: The updated Snap object.
    - **Raises**: 404 if the snap is not found or has expired.
    """
    db_snap = db.query(models.Snap).filter(
        models.Snap.id == snap_id,
        models.Snap.expires_at > func.now()
    ).first()
    
    if db_snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Snap not found or has expired"
        )
        
    if db_snap.is_viewed:
        logger.info(f"Snap {snap_id} already viewed by a recipient.")
        # We can choose to raise an error or just return the snap. Returning is safer.
        return db_snap

    # Mark as viewed
    db_snap.is_viewed = True
    
    # Log the viewing activity
    create_activity_log(db, db_snap.id, viewer_user_id, "VIEWED")
    
    db.commit()
    db.refresh(db_snap)
    
    logger.info(f"Snap with ID {snap_id} marked as viewed by user {viewer_user_id}.")
    return db_snap


@router.get(
    "/{snap_id}/activity_logs", 
    response_model=List[models.SnapActivityLogResponse],
    summary="Get Snap Activity Logs",
    description="Retrieves all activity logs for a specific Snap."
)
def get_snap_activity_logs(snap_id: int, db: Session = Depends(get_db)):
    """
    Retrieves all activity logs for a given Snap ID.
    
    - **snap_id**: The ID of the snap.
    - **db**: Database session dependency.
    - **Returns**: A list of SnapActivityLog objects.
    """
    logs = db.query(models.SnapActivityLog).filter(
        models.SnapActivityLog.snap_id == snap_id
    ).order_by(models.SnapActivityLog.timestamp.desc()).all()
    
    if not logs:
        # It's possible a snap exists but has no logs yet (though unlikely after creation)
        # We check if the snap exists to differentiate between no logs and no snap
        if not db.query(models.Snap).filter(models.Snap.id == snap_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Snap not found"
            )
            
    logger.info(f"Retrieved {len(logs)} activity logs for snap_id: {snap_id}")
    return logs
