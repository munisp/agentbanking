import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router Initialization ---
router = APIRouter(
    prefix="/falkordb-entities",
    tags=["FalkorDB Entities"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(db: Session, entity_id: int, activity_type: str, details: Optional[str] = None):
    """Helper function to log an activity for a specific entity."""
    log_entry = models.FalkorDBServiceActivityLog(
        entity_id=entity_id,
        activity_type=activity_type,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Activity logged for entity {entity_id}: {activity_type}")

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.FalkorDBServiceEntityResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new FalkorDB Service Entity",
    description="Registers a new FalkorDB connection configuration."
)
def create_entity(
    entity_data: models.FalkorDBServiceEntityCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new FalkorDB Service Entity in the database.
    """
    logger.info(f"Attempting to create new entity: {entity_data.name}")
    
    # Check for existing entity with the same name
    existing_entity = db.scalar(
        select(models.FalkorDBServiceEntity).where(models.FalkorDBServiceEntity.name == entity_data.name)
    )
    if existing_entity:
        logger.warning(f"Creation failed: Entity with name '{entity_data.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entity with name '{entity_data.name}' already exists."
        )

    db_entity = models.FalkorDBServiceEntity(**entity_data.model_dump())
    
    try:
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)
        log_activity(db, db_entity.id, "CREATE", "Entity successfully created.")
        logger.info(f"Entity created successfully with ID: {db_entity.id}")
        return db_entity
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database integrity error. Check input data."
        )

@router.get(
    "/{entity_id}", 
    response_model=models.FalkorDBServiceEntityResponse,
    summary="Retrieve a FalkorDB Service Entity by ID",
    description="Fetches the details of a specific FalkorDB entity, including its activity log."
)
def read_entity(entity_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a FalkorDB Service Entity by its ID.
    """
    logger.info(f"Attempting to read entity with ID: {entity_id}")
    db_entity = db.scalar(
        select(models.FalkorDBServiceEntity).where(models.FalkorDBServiceEntity.id == entity_id)
    )
    
    if db_entity is None:
        logger.warning(f"Read failed: Entity with ID {entity_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="FalkorDB Service Entity not found"
        )
    
    return db_entity

@router.get(
    "/", 
    response_model=List[models.FalkorDBServiceEntityResponse],
    summary="List all FalkorDB Service Entities",
    description="Retrieves a list of all registered FalkorDB entities."
)
def list_entities(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of FalkorDB Service Entities with pagination.
    """
    logger.info(f"Listing entities: skip={skip}, limit={limit}")
    entities = db.scalars(
        select(models.FalkorDBServiceEntity).offset(skip).limit(limit)
    ).all()
    return entities

@router.put(
    "/{entity_id}", 
    response_model=models.FalkorDBServiceEntityResponse,
    summary="Update a FalkorDB Service Entity",
    description="Updates the details of an existing FalkorDB entity."
)
def update_entity(
    entity_id: int, 
    entity_data: models.FalkorDBServiceEntityUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing FalkorDB Service Entity by its ID.
    """
    logger.info(f"Attempting to update entity with ID: {entity_id}")
    
    # Find the entity
    db_entity = db.scalar(
        select(models.FalkorDBServiceEntity).where(models.FalkorDBServiceEntity.id == entity_id)
    )
    
    if db_entity is None:
        logger.warning(f"Update failed: Entity with ID {entity_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="FalkorDB Service Entity not found"
        )

    update_data = entity_data.model_dump(exclude_unset=True)
    
    # Check for name conflict if name is being updated
    if 'name' in update_data and update_data['name'] != db_entity.name:
        existing_entity = db.scalar(
            select(models.FalkorDBServiceEntity).where(models.FalkorDBServiceEntity.name == update_data['name'])
        )
        if existing_entity and existing_entity.id != entity_id:
            logger.warning(f"Update failed: Entity with name '{update_data['name']}' already exists.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Another entity with name '{update_data['name']}' already exists."
            )

    # Apply updates
    for key, value in update_data.items():
        setattr(db_entity, key, value)

    try:
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)
        log_activity(db, db_entity.id, "UPDATE", f"Entity updated with fields: {list(update_data.keys())}")
        logger.info(f"Entity {entity_id} updated successfully.")
        return db_entity
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database integrity error. Check input data."
        )

@router.delete(
    "/{entity_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a FalkorDB Service Entity",
    description="Deletes a FalkorDB entity and all associated activity logs."
)
def delete_entity(entity_id: int, db: Session = Depends(get_db)):
    """
    Deletes a FalkorDB Service Entity by its ID.
    """
    logger.info(f"Attempting to delete entity with ID: {entity_id}")
    
    # Find the entity
    db_entity = db.scalar(
        select(models.FalkorDBServiceEntity).where(models.FalkorDBServiceEntity.id == entity_id)
    )
    
    if db_entity is None:
        logger.warning(f"Deletion failed: Entity with ID {entity_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="FalkorDB Service Entity not found"
        )

    try:
        # Deleting the entity will cascade to delete the activity logs
        db.delete(db_entity)
        db.commit()
        logger.info(f"Entity {entity_id} deleted successfully.")
        # Note: Activity log is not logged here as the entity is gone, but we can log before delete if needed.
        # For simplicity, we assume the deletion itself is the final action.
        return
    except Exception as e:
        db.rollback()
        logger.error(f"Error during deletion of entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during deletion."
        )

# --- Business-Specific Endpoints ---

@router.post(
    "/{entity_id}/test-connection",
    summary="Test FalkorDB Connection",
    description="Executes a connection test to the FalkorDB instance configured for the entity."
)
def test_connection(entity_id: int, db: Session = Depends(get_db)):
    """
    Executes testing the connection to the FalkorDB instance.
    In a real application, this would involve using the falkordb_connection_string
    to establish a connection and run a simple command (e.g., PING).
    """
    logger.info(f"Simulating connection test for entity ID: {entity_id}")
    
    db_entity = db.scalar(
        select(models.FalkorDBServiceEntity).where(models.FalkorDBServiceEntity.id == entity_id)
    )
    
    if db_entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="FalkorDB Service Entity not found"
        )

    # --- Simulation of Connection Logic ---
    # Replace this block with actual FalkorDB client logic in a real-world scenario
    connection_string = db_entity.falkordb_connection_string
    
    # Simple check for a valid-looking connection string
    if "redis://" not in connection_string and "rediss://" not in connection_string:
        log_activity(db, entity_id, "CONNECTION_TEST_FAILED", "Invalid connection string format.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection test failed: Invalid connection string format (completed)."
        )
    
    # Simulate success
    log_activity(db, entity_id, "CONNECTION_TEST_SUCCESS", "Connection test completed successfully.")
    
    return {
        "message": "Connection test completed successfully.",
        "entity_id": entity_id,
        "connection_string": connection_string,
        "status": "OK"
    }

@router.get(
    "/{entity_id}/activities",
    response_model=List[models.FalkorDBServiceActivityLogResponse],
    summary="Get Activity Log for Entity",
    description="Retrieves the activity log for a specific FalkorDB entity."
)
def get_entity_activities(
    entity_id: int, 
    db: Session = Depends(get_db),
    limit: int = 50
):
    """
    Retrieves the activity log for a FalkorDB Service Entity.
    """
    logger.info(f"Retrieving activity log for entity ID: {entity_id}")
    
    # Check if entity exists
    entity_exists = db.scalar(
        select(models.FalkorDBServiceEntity.id).where(models.FalkorDBServiceEntity.id == entity_id)
    )
    if not entity_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="FalkorDB Service Entity not found"
        )

    activities = db.scalars(
        select(models.FalkorDBServiceActivityLog)
        .where(models.FalkorDBServiceActivityLog.entity_id == entity_id)
        .order_by(models.FalkorDBServiceActivityLog.timestamp.desc())
        .limit(limit)
    ).all()
    
    return activities
