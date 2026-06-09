from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from models import Configuration, ConfigurationHistory
from schemas import ConfigurationCreate, ConfigurationUpdate
from config import logger

# --- Custom Exceptions ---

class ConfigurationServiceError(HTTPException):
    """Base exception for configuration service errors."""
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)

class ConfigurationNotFound(ConfigurationServiceError):
    """Raised when a configuration is not found."""
    def __init__(self, identifier: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration with identifier '{identifier}' not found."
        )

class ConfigurationAlreadyExists(ConfigurationServiceError):
    """Raised when trying to create a configuration with a key that already exists."""
    def __init__(self, key: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration with key '{key}' already exists."
        )

# --- Service Class ---

class ConfigurationService:
    """
    Business logic layer for Configuration management.
    """
    def __init__(self, db: Session) -> None:
        self.db = db

    def _create_history_record(self, config_id: int, old_value: Optional[str], new_value: str, changed_by: str = "API_USER") -> None:
        """Internal method to create a history record."""
        history = ConfigurationHistory(
            config_id=config_id,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by
        )
        self.db.add(history)
        # Note: Flush is not strictly necessary here as commit in the main method will handle it,
        # but it can be useful for debugging or complex transactions.

    def create_configuration(self, config_in: ConfigurationCreate) -> Configuration:
        """Creates a new configuration."""
        logger.info(f"Attempting to create configuration with key: {config_in.key}")
        
        # Check for existing key
        if self.get_configuration_by_key(config_in.key, raise_exception=False):
            raise ConfigurationAlreadyExists(config_in.key)

        db_config = Configuration(**config_in.model_dump())
        
        try:
            self.db.add(db_config)
            self.db.flush() # Flush to get the ID for the history record
            
            # Create initial history record
            self._create_history_record(
                config_id=db_config.id,
                old_value=None,
                new_value=db_config.value,
                changed_by="SYSTEM_CREATE"
            )
            
            self.db.commit()
            self.db.refresh(db_config)
            logger.info(f"Successfully created configuration ID: {db_config.id}")
            return db_config
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error during creation of {config_in.key}: {e}")
            raise ConfigurationAlreadyExists(config_in.key)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during creation of {config_in.key}: {e}")
            raise ConfigurationServiceError(status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred during creation.")

    def get_configuration_by_id(self, config_id: int, raise_exception: bool = True) -> Optional[Configuration]:
        """Retrieves a configuration by its ID."""
        db_config = self.db.query(Configuration).filter(Configuration.id == config_id).first()
        if not db_config and raise_exception:
            raise ConfigurationNotFound(str(config_id))
        return db_config

    def get_configuration_by_key(self, key: str, raise_exception: bool = True) -> Optional[Configuration]:
        """Retrieves a configuration by its unique key."""
        db_config = self.db.query(Configuration).filter(Configuration.key == key).first()
        if not db_config and raise_exception:
            raise ConfigurationNotFound(key)
        return db_config

    def get_all_configurations(self, skip: int = 0, limit: int = 100) -> List[Configuration]:
        """Retrieves a list of all configurations."""
        return self.db.query(Configuration).offset(skip).limit(limit).all()

    def update_configuration(self, config_id: int, config_in: ConfigurationUpdate) -> Configuration:
        """Updates an existing configuration and logs the change."""
        db_config = self.get_configuration_by_id(config_id) # Will raise 404 if not found

        update_data = config_in.model_dump(exclude_unset=True)
        
        old_value = db_config.value
        new_value = update_data.get("value", old_value)

        # Apply updates
        for key, value in update_data.items():
            setattr(db_config, key, value)

        try:
            # Only create history if the value has actually changed
            if old_value != new_value:
                self._create_history_record(
                    config_id=db_config.id,
                    old_value=old_value,
                    new_value=new_value
                )
                logger.info(f"Value change logged for config ID: {config_id}. Old: {old_value[:20]}... New: {new_value[:20]}...")

            self.db.add(db_config)
            self.db.commit()
            self.db.refresh(db_config)
            logger.info(f"Successfully updated configuration ID: {config_id}")
            return db_config
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during update of {config_id}: {e}")
            raise ConfigurationServiceError(status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred during update.")

    def delete_configuration(self, config_id: int) -> dict:
        """Deletes a configuration and its associated history."""
        db_config = self.get_configuration_by_id(config_id) # Will raise 404 if not found

        try:
            # Due to cascade="all, delete-orphan" in models.py, history records will be deleted automatically
            self.db.delete(db_config)
            self.db.commit()
            logger.info(f"Successfully deleted configuration ID: {config_id}")
            return {"message": f"Configuration ID {config_id} deleted successfully."}
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during deletion of {config_id}: {e}")
            raise ConfigurationServiceError(status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred during deletion.")