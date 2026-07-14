import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import configuration and models/schemas
from .config import get_db
from .models import (
    DatabaseItemCreate,
    DatabaseItemUpdate,
    DatabaseItemResponse,
    ActivityLogResponse,
    create_item,
    get_item,
    get_items,
    update_item,
    delete_item,
    get_item_activity_logs,
    get_all_activity_logs,
    init_db,
    engine
)

# Initialize database (for simplicity in this single-service setup)
init_db(engine)

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(
    prefix="/database",
    tags=["database"],
    responses={404: {"description": "Not found"}},
)

# --- CRUD Endpoints for DatabaseItem ---

@router.post(
    "/items/",
    response_model=DatabaseItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Database Item",
    description="Creates a new generic database item and logs the creation activity."
)
def create_database_item(
    item: DatabaseItemCreate, db: Session = Depends(get_db)
):
    """
    Create a new DatabaseItem in the database.
    """
    try:
        db_item = create_item(db=db, item=item)
        logger.info(f"Created new item with ID: {db_item.id}")
        return db_item
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during item creation: {e}",
        )

@router.get(
    "/items/",
    response_model=List[DatabaseItemResponse],
    summary="List all Database Items",
    description="Retrieves a list of all database items with optional pagination."
)
def read_database_items(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve a list of DatabaseItems.
    """
    items = get_items(db, skip=skip, limit=limit)
    return items

@router.get(
    "/items/{item_id}",
    response_model=DatabaseItemResponse,
    summary="Get a specific Database Item",
    description="Retrieves a single database item by its unique ID."
)
def read_database_item(item_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a single DatabaseItem by ID.
    """
    db_item = get_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    return db_item

@router.put(
    "/items/{item_id}",
    response_model=DatabaseItemResponse,
    summary="Update an existing Database Item",
    description="Updates an existing database item by its ID and logs the update activity."
)
def update_database_item(
    item_id: int, item: DatabaseItemUpdate, db: Session = Depends(get_db)
):
    """
    Update an existing DatabaseItem.
    """
    db_item = update_item(db, item_id=item_id, item=item)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    logger.info(f"Updated item with ID: {item_id}")
    return db_item

@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Database Item",
    description="Deletes a database item by its ID and logs the deletion activity."
)
def delete_database_item(item_id: int, db: Session = Depends(get_db)):
    """
    Delete a DatabaseItem.
    """
    db_item = delete_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    logger.warning(f"Deleted item with ID: {item_id}")
    return {"ok": True} # FastAPI will handle the 204 response correctly

# --- Business-Specific/Additional Endpoints (Activity Log) ---

@router.get(
    "/items/{item_id}/logs",
    response_model=List[ActivityLogResponse],
    summary="Get Activity Logs for a specific Item",
    description="Retrieves the activity log history for a single database item."
)
def read_item_logs(
    item_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve activity logs for a specific DatabaseItem.
    """
    if get_item(db, item_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    logs = get_item_activity_logs(db, item_id=item_id, skip=skip, limit=limit)
    return logs

@router.get(
    "/logs/",
    response_model=List[ActivityLogResponse],
    summary="Get All Activity Logs",
    description="Retrieves all activity log entries across all database items."
)
def read_all_logs(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """
    Retrieve all activity logs.
    """
    logs = get_all_activity_logs(db, skip=skip, limit=limit)
    return logs
