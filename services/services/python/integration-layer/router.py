import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db, get_settings

# --- Setup ---

settings = get_settings()
router = APIRouter(
    prefix="/api/v1/integration-layer",
    tags=["integration-configs"],
    responses={404: {"description": "Not found"}},
)

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(settings.SERVICE_NAME)

# --- Helper Functions ---

def log_activity(db: Session, config_id: int, activity_type: str, details: Optional[str] = None, is_error: bool = False):
    """
    Helper function to create an activity log entry.
    """
    log_data = models.IntegrationActivityLogCreate(
        config_id=config_id,
        activity_type=activity_type,
        details=details,
        is_error=is_error
    )
    db_log = models.IntegrationActivityLog(**log_data.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    if is_error:
        logger.error(f"Config ID {config_id} - Activity: {activity_type} - Details: {details}")
    else:
        logger.info(f"Config ID {config_id} - Activity: {activity_type} - Details: {details}")

# --- CRUD Endpoints for IntegrationConfig ---

@router.post(
    "/configs", 
    response_model=models.IntegrationConfigResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new integration configuration"
)
def create_config(
    config: models.IntegrationConfigCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new configuration for an external integration service.
    
    Raises:
        HTTPException 409: If a configuration with the same name already exists.
    """
    try:
        db_config = models.IntegrationConfig(**config.model_dump())
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        log_activity(db, db_config.id, "CONFIG_CREATED", f"New config '{config.name}' created.")
        return db_config
    except IntegrityError:
        db.rollback()
        logger.warning(f"Attempt to create duplicate config name: {config.name}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration with name '{config.name}' already exists."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the configuration."
        )

@router.get(
    "/configs/{config_id}", 
    response_model=models.IntegrationConfigResponse,
    summary="Retrieve a single integration configuration by ID"
)
def read_config(
    config_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves the details of a specific integration configuration.
    
    Args:
        config_id: The unique ID of the configuration.
        
    Raises:
        HTTPException 404: If the configuration is not found.
    """
    db_config = db.query(models.IntegrationConfig).filter(models.IntegrationConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Configuration with ID {config_id} not found."
        )
    return db_config

@router.get(
    "/configs", 
    response_model=List[models.IntegrationConfigResponse],
    summary="List all integration configurations"
)
def list_configs(
    skip: int = Query(0, ge=0, description="Number of items to skip (offset)"),
    limit: int = Query(100, le=100, description="Maximum number of items to return (limit)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of all integration configurations with optional filtering and pagination.
    """
    query = db.query(models.IntegrationConfig)
    if is_active is not None:
        query = query.filter(models.IntegrationConfig.is_active == is_active)
        
    configs = query.offset(skip).limit(limit).all()
    return configs

@router.put(
    "/configs/{config_id}", 
    response_model=models.IntegrationConfigResponse,
    summary="Update an existing integration configuration"
)
def update_config(
    config_id: int, 
    config: models.IntegrationConfigUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates the details of an existing integration configuration.
    
    Args:
        config_id: The unique ID of the configuration to update.
        
    Raises:
        HTTPException 404: If the configuration is not found.
        HTTPException 409: If the update causes a duplicate name conflict.
    """
    db_config = db.query(models.IntegrationConfig).filter(models.IntegrationConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Configuration with ID {config_id} not found."
        )

    update_data = config.model_dump(exclude_unset=True)
    
    try:
        for key, value in update_data.items():
            setattr(db_config, key, value)
        
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        log_activity(db, db_config.id, "CONFIG_UPDATED", f"Config updated with fields: {list(update_data.keys())}")
        return db_config
    except IntegrityError:
        db.rollback()
        logger.warning(f"Attempt to update config ID {config_id} to a duplicate name.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A configuration with the new name already exists."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating config ID {config_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the configuration."
        )

@router.delete(
    "/configs/{config_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an integration configuration"
)
def delete_config(
    config_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes a specific integration configuration and all associated activity logs.
    
    Args:
        config_id: The unique ID of the configuration to delete.
        
    Raises:
        HTTPException 404: If the configuration is not found.
    """
    db_config = db.query(models.IntegrationConfig).filter(models.IntegrationConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Configuration with ID {config_id} not found."
        )
    
    db.delete(db_config)
    db.commit()
    logger.warning(f"Config ID {config_id} deleted.")
    # Logs are deleted via cascade on relationship

# --- Business-Specific Endpoints ---

@router.post(
    "/configs/{config_id}/sync",
    response_model=models.IntegrationConfigResponse,
    summary="Initiate a synchronization process for a configuration"
)
def initiate_sync(
    config_id: int,
    db: Session = Depends(get_db)
):
    """
    Initiates a synchronization process with the external service via HTTP API.
    
    In a real application, this would trigger an asynchronous job. For this
    implementation, it updates the `last_synced_at` timestamp and logs the activity.
    
    Args:
        config_id: The unique ID of the configuration to sync.
        
    Raises:
        HTTPException 404: If the configuration is not found.
        HTTPException 400: If the configuration is not active.
    """
    db_config = db.query(models.IntegrationConfig).filter(models.IntegrationConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Configuration with ID {config_id} not found."
        )
        
    if not db_config.is_active:
        log_activity(db, config_id, "SYNC_ATTEMPT_FAILED", "Sync failed: Configuration is not active.", is_error=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration with ID {config_id} is not active and cannot be synced."
        )

    # Start sync via external service API
    log_activity(db, config_id, "SYNC_START", "Synchronization process initiated.")
    
    # Sync initiated
    import datetime
    db_config.last_synced_at = datetime.datetime.utcnow()
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    log_activity(db, config_id, "SYNC_SUCCESS", "Synchronization completed successfully.")
    
    return db_config

# --- Activity Log Endpoints ---

@router.get(
    "/configs/{config_id}/logs",
    response_model=List[models.IntegrationActivityLogResponse],
    summary="Retrieve activity logs for a specific configuration"
)
def list_activity_logs(
    config_id: int,
    skip: int = Query(0, ge=0, description="Number of items to skip (offset)"),
    limit: int = Query(100, le=100, description="Maximum number of items to return (limit)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves a paginated list of activity logs for a given integration configuration.
    
    Args:
        config_id: The unique ID of the configuration.
        
    Raises:
        HTTPException 404: If the configuration is not found.
    """
    # Check if config exists
    db_config = db.query(models.IntegrationConfig).filter(models.IntegrationConfig.id == config_id).first()
    if db_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Configuration with ID {config_id} not found."
        )
        
    logs = db.query(models.IntegrationActivityLog) \
             .filter(models.IntegrationActivityLog.config_id == config_id) \
             .order_by(models.IntegrationActivityLog.timestamp.desc()) \
             .offset(skip) \
             .limit(limit) \
             .all()
             
    return logs
