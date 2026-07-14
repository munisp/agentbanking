import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .config import get_db

# --- Configuration and Logging ---

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Dependencies ---

def get_current_user_id(authorization: Optional[str] = Header(None, alias="Authorization")) -> int:
    """Get authenticated user ID from JWT token."""
    from jose import JWTError, jwt
    import os

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]

    secret_key = os.getenv("JWT_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY env var is required")

    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user id in token")

    try:
        return int(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id in token")

# --- Helper Functions ---

def create_activity_log(
    db: Session,
    item_id: int,
    activity_type: str,
    performed_by_user_id: int,
    details: Optional[str] = None,
):
    """Creates a new entry in the communication activity log."""
    log_entry = models.CommunicationActivityLog(
        item_id=item_id,
        activity_type=activity_type,
        performed_by_user_id=performed_by_user_id,
        details=details,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(
        f"Activity logged: item_id={item_id}, type={activity_type}, user={performed_by_user_id}"
    )
    return log_entry

# --- Router Definition ---

router = APIRouter(
    prefix="/shared-items",
    tags=["Shared Communication Items"],
    responses={404: {"description": "Not found"}},
)

# --- CRUD Endpoints for SharedCommunicationItem ---

@router.post(
    "/",
    response_model=models.SharedCommunicationItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shared communication item",
)
def create_shared_item(
    item: models.SharedCommunicationItemCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Creates a new shared communication item (e.g., a template, a link).
    The `created_by_user_id` is automatically set to the authenticated user's ID.
    """
    db_item = models.SharedCommunicationItem(
        **item.model_dump(), created_by_user_id=user_id
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    create_activity_log(
        db,
        db_item.id,
        "create",
        user_id,
        f"New item created with type: {db_item.item_type}",
    )
    
    logger.info(f"Shared item created: ID {db_item.id} by user {user_id}")
    return db_item


@router.get(
    "/{item_id}",
    response_model=models.SharedCommunicationItemResponse,
    summary="Retrieve a shared communication item by ID",
)
def read_shared_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Retrieves a specific shared communication item.
    Logs a 'view' activity for the item.
    """
    db_item = (
        db.query(models.SharedCommunicationItem)
        .filter(models.SharedCommunicationItem.id == item_id)
        .first()
    )
    if db_item is None:
        logger.warning(f"Attempted to read non-existent item: ID {item_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shared communication item not found"
        )
    
    create_activity_log(db, db_item.id, "view", user_id)
    
    return db_item


@router.get(
    "/",
    response_model=List[models.SharedCommunicationItemResponse],
    summary="List all shared communication items",
)
def list_shared_items(
    item_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Retrieves a list of shared communication items with optional filtering by type and active status.
    """
    query = db.query(models.SharedCommunicationItem)
    
    if item_type:
        query = query.filter(models.SharedCommunicationItem.item_type == item_type)
    
    if is_active is not None:
        query = query.filter(models.SharedCommunicationItem.is_active == is_active)
        
    items = query.offset(skip).limit(limit).all()
    
    logger.info(f"Listed {len(items)} shared items (skip={skip}, limit={limit})")
    return items


@router.put(
    "/{item_id}",
    response_model=models.SharedCommunicationItemResponse,
    summary="Update an existing shared communication item",
)
def update_shared_item(
    item_id: int,
    item_update: models.SharedCommunicationItemUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Updates an existing shared communication item.
    Only non-None fields in the request body will be updated.
    Logs an 'update' activity.
    """
    db_item = (
        db.query(models.SharedCommunicationItem)
        .filter(models.SharedCommunicationItem.id == item_id)
        .first()
    )
    if db_item is None:
        logger.warning(f"Attempted to update non-existent item: ID {item_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shared communication item not found"
        )

    update_data = item_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update"
        )

    for key, value in update_data.items():
        setattr(db_item, key, value)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    
    create_activity_log(
        db,
        db_item.id,
        "update",
        user_id,
        f"Fields updated: {', '.join(update_data.keys())}",
    )
    
    logger.info(f"Shared item updated: ID {db_item.id} by user {user_id}")
    return db_item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a shared communication item",
)
def delete_shared_item(
    item_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Deletes a shared communication item.
    Logs a 'delete' activity.
    """
    db_item = (
        db.query(models.SharedCommunicationItem)
        .filter(models.SharedCommunicationItem.id == item_id)
        .first()
    )
    if db_item is None:
        # Return 204 even if not found, as the desired state (absence) is achieved (Idempotency)
        return
    
    # Log activity before deletion
    create_activity_log(db, db_item.id, "delete", user_id)
    
    db.delete(db_item)
    db.commit()
    
    logger.info(f"Shared item deleted: ID {item_id} by user {user_id}")
    return


# --- Business-Specific Endpoints (Activity Log) ---

@router.get(
    "/{item_id}/activities",
    response_model=List[models.CommunicationActivityLogResponse],
    summary="List activity logs for a specific shared item",
)
def list_item_activities(
    item_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Retrieves the history of activities (views, updates, etc.) for a given shared communication item.
    """
    # First, check if the item exists
    item_exists = (
        db.query(models.SharedCommunicationItem)
        .filter(models.SharedCommunicationItem.id == item_id)
        .first()
    )
    if item_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shared communication item not found"
        )
        
    activities = (
        db.query(models.CommunicationActivityLog)
        .filter(models.CommunicationActivityLog.item_id == item_id)
        .order_by(models.CommunicationActivityLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    logger.info(f"Listed {len(activities)} activities for item ID {item_id}")
    return activities
