from typing import List
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import ConfigurationRead, ConfigurationCreate, ConfigurationUpdate
from service import ConfigurationService, ConfigurationNotFound, ConfigurationAlreadyExists
from config import logger

# Create the router with a specific prefix and tags
router = APIRouter(
    prefix="/configurations",
    tags=["configurations"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the service layer
def get_config_service(db: Session = Depends(get_db)) -> ConfigurationService:
    """Provides a ConfigurationService instance with a database session."""
    return ConfigurationService(db)

@router.post(
    "/", 
    response_model=ConfigurationRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new configuration setting"
)
def create_configuration(
    config_in: ConfigurationCreate,
    service: ConfigurationService = Depends(get_config_service)
) -> None:
    """
    Creates a new configuration setting in the database.
    Raises 409 Conflict if a configuration with the same key already exists.
    """
    try:
        logger.info(f"POST request to create configuration: {config_in.key}")
        return service.create_configuration(config_in=config_in)
    except ConfigurationAlreadyExists as e:
        raise e

@router.get(
    "/", 
    response_model=List[ConfigurationRead],
    summary="Retrieve a list of all configurations"
)
def read_configurations(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of items to return"),
    service: ConfigurationService = Depends(get_config_service)
) -> None:
    """
    Retrieves a paginated list of all configuration settings.
    """
    logger.info(f"GET request for configurations list (skip={skip}, limit={limit})")
    return service.get_all_configurations(skip=skip, limit=limit)

@router.get(
    "/{config_id}", 
    response_model=ConfigurationRead,
    summary="Retrieve a configuration by ID"
)
def read_configuration_by_id(
    config_id: int,
    service: ConfigurationService = Depends(get_config_service)
) -> None:
    """
    Retrieves a single configuration setting by its unique ID.
    Raises 404 Not Found if the configuration does not exist.
    """
    logger.info(f"GET request for configuration ID: {config_id}")
    try:
        return service.get_configuration_by_id(config_id=config_id)
    except ConfigurationNotFound as e:
        raise e

@router.get(
    "/key/{key}", 
    response_model=ConfigurationRead,
    summary="Retrieve a configuration by key"
)
def read_configuration_by_key(
    key: str,
    service: ConfigurationService = Depends(get_config_service)
) -> None:
    """
    Retrieves a single configuration setting by its unique key.
    Raises 404 Not Found if the configuration does not exist.
    """
    logger.info(f"GET request for configuration key: {key}")
    try:
        return service.get_configuration_by_key(key=key)
    except ConfigurationNotFound as e:
        raise e

@router.patch(
    "/{config_id}", 
    response_model=ConfigurationRead,
    summary="Update an existing configuration setting"
)
def update_configuration(
    config_id: int,
    config_in: ConfigurationUpdate,
    service: ConfigurationService = Depends(get_config_service)
) -> None:
    """
    Updates an existing configuration setting. This is a partial update (PATCH).
    Raises 404 Not Found if the configuration does not exist.
    """
    logger.info(f"PATCH request to update configuration ID: {config_id}")
    try:
        return service.update_configuration(config_id=config_id, config_in=config_in)
    except ConfigurationNotFound as e:
        raise e

@router.delete(
    "/{config_id}", 
    status_code=status.HTTP_200_OK,
    summary="Delete a configuration setting"
)
def delete_configuration(
    config_id: int,
    service: ConfigurationService = Depends(get_config_service)
) -> None:
    """
    Deletes a configuration setting by its ID.
    Raises 404 Not Found if the configuration does not exist.
    """
    logger.info(f"DELETE request for configuration ID: {config_id}")
    try:
        return service.delete_configuration(config_id=config_id)
    except ConfigurationNotFound as e:
        raise e