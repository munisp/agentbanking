import uuid
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import Field

from . import models
from .config import get_db, logger

# --- Router Initialization ---

router = APIRouter(
    prefix="/territories",
    tags=["territory-management"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(db: Session, territory_id: uuid.UUID, action: str, user_id: str, details: Optional[dict] = None):
    """
    Logs an activity related to a territory.
    """
    log_entry = models.TerritoryActivityLog(
        territory_id=territory_id,
        action=action,
        user_id=user_id,
        details=json.dumps(details) if details else None
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Activity logged for territory {territory_id}: {action} by user {user_id}")

def get_current_user_id() -> str:
    """
    User authentication/authorization via JWT.
    In a real application, this would extract the user ID from a JWT or session.
    """
    # For demonstration, we use a static user ID.
    return "system_user_001"

# --- CRUD Endpoints for Territory ---

@router.post(
    "/",
    response_model=models.TerritoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Territory",
    description="Creates a new territory record in the database and logs the creation activity."
)
def create_territory(
    territory: models.TerritoryCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Creates a new Territory.

    Args:
        territory: The data for the new territory.
        db: The database session dependency.
        user_id: The ID of the user performing the action.

    Returns:
        The created Territory object.
    """
    logger.info(f"Attempting to create new territory: {territory.name}")
    
    # Check for existing territory with the same name
    existing_territory = db.query(models.Territory).filter(
        models.Territory.name == territory.name,
        models.Territory.is_deleted == False
    ).first()
    
    if existing_territory:
        logger.warning(f"Territory creation failed: Name '{territory.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Territory with name '{territory.name}' already exists."
        )

    db_territory = models.Territory(**territory.model_dump())
    
    try:
        db.add(db_territory)
        db.commit()
        db.refresh(db_territory)
        
        # Log activity
        log_activity(db, db_territory.id, "CREATED", user_id, {"name": db_territory.name})
        
        logger.info(f"Successfully created territory with ID: {db_territory.id}")
        return db_territory
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during territory creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during territory creation."
        )

@router.get(
    "/{territory_id}",
    response_model=models.TerritoryResponse,
    summary="Get a Territory by ID",
    description="Retrieves a single territory by its unique ID, excluding soft-deleted records."
)
def read_territory(
    territory_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves a Territory by ID.

    Args:
        territory_id: The unique ID of the territory.
        db: The database session dependency.

    Returns:
        The Territory object.
    """
    db_territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id,
        models.Territory.is_deleted == False
    ).first()
    
    if db_territory is None:
        logger.warning(f"Territory not found with ID: {territory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Territory not found or has been deleted."
        )
    
    return db_territory

@router.get(
    "/",
    response_model=models.TerritoryListResponse,
    summary="List and Search Territories",
    description="Retrieves a paginated list of territories, with optional filtering by name, type, and status."
)
def list_territories(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number for pagination."),
    size: int = Query(10, ge=1, le=100, description="Number of items per page."),
    name: Optional[str] = Query(None, description="Filter by territory name (partial match)."),
    territory_type: Optional[str] = Query(None, description="Filter by territory type."),
    status: Optional[str] = Query(None, description="Filter by territory status."),
):
    """
    Lists territories with pagination and optional filters.

    Args:
        db: The database session dependency.
        page: The page number.
        size: The number of items per page.
        name: Optional filter for territory name.
        territory_type: Optional filter for territory type.
        status: Optional filter for territory status.

    Returns:
        A paginated list of Territory objects.
    """
    query = db.query(models.Territory).filter(models.Territory.is_deleted == False)
    
    if name:
        query = query.filter(models.Territory.name.ilike(f"%{name}%"))
    if territory_type:
        query = query.filter(models.Territory.territory_type == territory_type)
    if status:
        query = query.filter(models.Territory.status == status)

    total = query.count()
    offset = (page - 1) * size
    
    territories = query.offset(offset).limit(size).all()
    
    return models.TerritoryListResponse(
        territories=territories,
        total=total,
        page=page,
        size=size
    )

@router.put(
    "/{territory_id}",
    response_model=models.TerritoryResponse,
    summary="Update an existing Territory",
    description="Updates an existing territory by ID and logs the update activity."
)
def update_territory(
    territory_id: uuid.UUID,
    territory_update: models.TerritoryUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Updates an existing Territory.

    Args:
        territory_id: The unique ID of the territory to update.
        territory_update: The data to update the territory with.
        db: The database session dependency.
        user_id: The ID of the user performing the action.

    Returns:
        The updated Territory object.
    """
    db_territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id,
        models.Territory.is_deleted == False
    ).first()
    
    if db_territory is None:
        logger.warning(f"Update failed: Territory not found with ID: {territory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Territory not found or has been deleted."
        )

    update_data = territory_update.model_dump(exclude_unset=True)
    
    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != db_territory.name:
        existing_territory = db.query(models.Territory).filter(
            models.Territory.name == update_data["name"],
            models.Territory.is_deleted == False
        ).first()
        if existing_territory and existing_territory.id != territory_id:
            logger.warning(f"Update failed: Name '{update_data['name']}' already in use by another territory.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Territory with name '{update_data['name']}' already exists."
            )

    # Apply updates and track changes for logging
    changes = {}
    for key, value in update_data.items():
        if hasattr(db_territory, key) and getattr(db_territory, key) != value:
            changes[key] = {"old": getattr(db_territory, key), "new": value}
            setattr(db_territory, key, value)

    if not changes:
        logger.info(f"No changes detected for territory ID: {territory_id}")
        return db_territory

    try:
        db.commit()
        db.refresh(db_territory)
        
        # Log activity
        log_activity(db, db_territory.id, "UPDATED", user_id, changes)
        
        logger.info(f"Successfully updated territory with ID: {db_territory.id}")
        return db_territory
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during territory update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during territory update."
        )

@router.delete(
    "/{territory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-Delete a Territory",
    description="Performs a soft-delete on a territory by setting the 'is_deleted' flag to True and logs the deletion activity."
)
def delete_territory(
    territory_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Soft-deletes a Territory.

    Args:
        territory_id: The unique ID of the territory to soft-delete.
        db: The database session dependency.
        user_id: The ID of the user performing the action.
    """
    db_territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id,
        models.Territory.is_deleted == False
    ).first()
    
    if db_territory is None:
        logger.warning(f"Deletion failed: Territory not found with ID: {territory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Territory not found or already deleted."
        )

    db_territory.is_deleted = True
    
    try:
        db.commit()
        
        # Log activity
        log_activity(db, db_territory.id, "DELETED", user_id)
        
        logger.info(f"Successfully soft-deleted territory with ID: {territory_id}")
        return status.HTTP_204_NO_CONTENT
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during territory soft-deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during territory soft-deletion."
        )

# --- Business-Specific Endpoints ---

@router.get(
    "/{territory_id}/activity-logs",
    response_model=List[models.TerritoryActivityLogResponse],
    summary="Get Activity Logs for a Territory",
    description="Retrieves a list of all activity logs associated with a specific territory."
)
def get_territory_activity_logs(
    territory_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return.")
):
    """
    Retrieves activity logs for a specific Territory.

    Args:
        territory_id: The unique ID of the territory.
        db: The database session dependency.
        limit: The maximum number of logs to return.

    Returns:
        A list of TerritoryActivityLog objects.
    """
    # First, check if the territory exists (and is not deleted)
    db_territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id,
        models.Territory.is_deleted == False
    ).first()
    
    if db_territory is None:
        logger.warning(f"Activity log retrieval failed: Territory not found with ID: {territory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Territory not found or has been deleted."
        )

    # Retrieve logs, ordered by timestamp descending
    logs = db.query(models.TerritoryActivityLog).filter(
        models.TerritoryActivityLog.territory_id == territory_id
    ).order_by(
        models.TerritoryActivityLog.timestamp.desc()
    ).limit(limit).all()
    
    return logs

@router.post(
    "/{territory_id}/status-change",
    response_model=models.TerritoryResponse,
    summary="Change Territory Status",
    description="Updates the status of a territory and logs the status change activity."
)
def change_territory_status(
    territory_id: uuid.UUID,
    new_status: str = Field(..., description="The new status for the territory."),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Changes the status of an existing Territory.

    Args:
        territory_id: The unique ID of the territory.
        new_status: The new status to set.
        db: The database session dependency.
        user_id: The ID of the user performing the action.

    Returns:
        The updated Territory object.
    """
    db_territory = db.query(models.Territory).filter(
        models.Territory.id == territory_id,
        models.Territory.is_deleted == False
    ).first()
    
    if db_territory is None:
        logger.warning(f"Status change failed: Territory not found with ID: {territory_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Territory not found or has been deleted."
        )

    old_status = db_territory.status
    if old_status == new_status:
        logger.info(f"Status for territory {territory_id} is already {new_status}. No change needed.")
        return db_territory

    db_territory.status = new_status
    
    try:
        db.commit()
        db.refresh(db_territory)
        
        # Log activity
        log_activity(db, db_territory.id, "STATUS_CHANGE", user_id, {"old_status": old_status, "new_status": new_status})
        
        logger.info(f"Successfully changed status for territory {territory_id} from {old_status} to {new_status}")
        return db_territory
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during territory status change: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during territory status change."
        )
