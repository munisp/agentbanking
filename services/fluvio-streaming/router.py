import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(
    prefix="/fluvio-streaming",
    tags=["fluvio-streaming"],
    responses={404: {"description": "Not found"}},
)

def create_activity_log(db: Session, config_id: int, action: str, details: str):
    """Helper function to create an activity log entry."""
    log_entry = models.FluvioStreamingActivityLog(
        config_id=config_id,
        action=action,
        details=details
    )
    db.add(log_entry)
    # Note: The log is committed with the main transaction in the CRUD operations.

# --- CRUD Operations ---

@router.post(
    "/", 
    response_model=models.FluvioStreamingResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Fluvio Streaming configuration"
)
def create_config(
    config: models.FluvioStreamingCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new Fluvio Streaming configuration in the database.
    
    Raises:
        HTTPException 409: If a configuration with the same name already exists.
    """
    logger.info(f"Attempting to create new configuration: {config.name}")
    
    db_config = models.FluvioStreaming(**config.model_dump())
    
    try:
        db.add(db_config)
        db.flush() # Flush to get the ID before commit for logging
        
        create_activity_log(
            db, 
            db_config.id, 
            "CREATE", 
            f"Configuration '{db_config.name}' created with stream type '{db_config.stream_type}'."
        )
        
        db.commit()
        db.refresh(db_config)
        logger.info(f"Successfully created configuration with ID: {db_config.id}")
        return db_config
    except IntegrityError:
        db.rollback()
        logger.warning(f"Conflict: Configuration with name '{config.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration with name '{config.name}' already exists."
        )

@router.get(
    "/", 
    response_model=List[models.FluvioStreamingResponse],
    summary="List all Fluvio Streaming configurations"
)
def list_configs(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all Fluvio Streaming configurations with pagination.
    """
    logger.info(f"Listing configurations (skip={skip}, limit={limit})")
    configs = db.query(models.FluvioStreaming).offset(skip).limit(limit).all()
    return configs

@router.get(
    "/{config_id}", 
    response_model=models.FluvioStreamingResponse,
    summary="Get a specific Fluvio Streaming configuration by ID"
)
def read_config(
    config_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single Fluvio Streaming configuration by its unique ID.
    
    Raises:
        HTTPException 404: If the configuration is not found.
    """
    config = db.query(models.FluvioStreaming).filter(models.FluvioStreaming.id == config_id).first()
    if config is None:
        logger.warning(f"Configuration with ID {config_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Configuration not found"
        )
    return config

@router.put(
    "/{config_id}", 
    response_model=models.FluvioStreamingResponse,
    summary="Update an existing Fluvio Streaming configuration"
)
def update_config(
    config_id: int, 
    config_update: models.FluvioStreamingUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing Fluvio Streaming configuration identified by ID.
    
    Raises:
        HTTPException 404: If the configuration is not found.
        HTTPException 409: If the update causes a name conflict.
    """
    db_config = read_config(config_id=config_id, db=db) # Reuses read_config for 404 check
    
    update_data = config_update.model_dump(exclude_unset=True)
    if not update_data:
        return db_config # No changes to apply
        
    old_values = {k: getattr(db_config, k) for k in update_data.keys()}
    
    for key, value in update_data.items():
        setattr(db_config, key, value)
        
    try:
        db.add(db_config)
        
        details = ", ".join([f"{k}: {old_values[k]} -> {update_data[k]}" for k in update_data.keys()])
        create_activity_log(
            db, 
            db_config.id, 
            "UPDATE", 
            f"Configuration updated. Changes: {details}"
        )
        
        db.commit()
        db.refresh(db_config)
        logger.info(f"Successfully updated configuration with ID: {config_id}")
        return db_config
    except IntegrityError:
        db.rollback()
        logger.warning(f"Conflict: Update for ID {config_id} failed due to integrity constraint (e.g., duplicate name).")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update failed due to integrity constraint (e.g., duplicate name)."
        )

@router.delete(
    "/{config_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Fluvio Streaming configuration"
)
def delete_config(
    config_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a Fluvio Streaming configuration identified by ID.
    
    Raises:
        HTTPException 404: If the configuration is not found.
    """
    db_config = read_config(config_id=config_id, db=db) # Reuses read_config for 404 check
    
    # Activity log before deletion (logs are cascade-deleted, so log on the main table)
    create_activity_log(
        db, 
        db_config.id, 
        "DELETE", 
        f"Configuration '{db_config.name}' marked for deletion."
    )
    
    db.delete(db_config)
    db.commit()
    logger.info(f"Successfully deleted configuration with ID: {config_id}")
    return {"ok": True}

# --- Business-Specific Endpoint ---

@router.patch(
    "/{config_id}/toggle-active",
    response_model=models.FluvioStreamingResponse,
    summary="Toggle the active status of a configuration"
)
def toggle_active_status(
    config_id: int,
    db: Session = Depends(get_db)
):
    """
    Toggles the `is_active` status of a Fluvio Streaming configuration.
    
    Raises:
        HTTPException 404: If the configuration is not found.
    """
    db_config = read_config(config_id=config_id, db=db)
    
    new_status = not db_config.is_active
    db_config.is_active = new_status
    
    db.add(db_config)
    
    action_detail = "activated" if new_status else "deactivated"
    create_activity_log(
        db, 
        db_config.id, 
        "STATUS_CHANGE", 
        f"Configuration status toggled to {action_detail}."
    )
    
    db.commit()
    db.refresh(db_config)
    logger.info(f"Configuration {config_id} status toggled to {action_detail}.")
    return db_config
