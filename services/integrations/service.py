from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Integration, IntegrationLog
from schemas import IntegrationCreate, IntegrationUpdate, IntegrationLogCreate
from config import logger
import json
import hashlib

# --- Custom Exceptions ---

class IntegrationServiceError(Exception):
    """Base exception for the integration service."""
    pass

class IntegrationNotFoundError(IntegrationServiceError):
    """Raised when an integration with the given ID or name is not found."""
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Integration with identifier '{identifier}' not found.")

class IntegrationAlreadyExistsError(IntegrationServiceError):
    """Raised when trying to create an integration with a name that already exists."""
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Integration with name '{name}' already exists.")

# --- Utility Functions (Simulated Security) ---

def _encrypt_api_key(api_key: str) -> str:
    """
    Simulated encryption of an API key using SHA-256 for demonstration.
    In a production environment, this would be a proper, reversible encryption
    mechanism (e.g., AES-256 with a secure key management system).
    """
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

# --- Service Layer ---

class IntegrationService:
    """
    Business logic layer for managing Integrations and Integration Logs.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Integration CRUD Operations ---

    def create_integration(self, integration_data: IntegrationCreate) -> Integration:
        """Creates a new Integration."""
        logger.info(f"Attempting to create new integration: {integration_data.name}")
        
        # Check for existing integration with the same name
        if self.db.query(Integration).filter(Integration.name == integration_data.name).first():
            logger.warning(f"Creation failed: Integration with name '{integration_data.name}' already exists.")
            raise IntegrationAlreadyExistsError(integration_data.name)

        # Encrypt the API key before storing
        encrypted_key = _encrypt_api_key(integration_data.api_key)

        db_integration = Integration(
            name=integration_data.name,
            type=integration_data.type,
            description=integration_data.description,
            api_key_encrypted=encrypted_key,
            config_json=integration_data.config_json,
            is_active=integration_data.is_active
        )

        try:
            self.db.add(db_integration)
            self.db.commit()
            self.db.refresh(db_integration)
            logger.info(f"Integration '{db_integration.name}' created successfully with ID: {db_integration.id}")
            return db_integration
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error during creation: {e}")
            raise IntegrationAlreadyExistsError(integration_data.name) # Catch unique constraint violation
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during integration creation: {e}")
            raise IntegrationServiceError(f"Failed to create integration: {e}")

    def get_integration_by_id(self, integration_id: UUID) -> Integration:
        """Retrieves an Integration by its ID."""
        logger.debug(f"Fetching integration with ID: {integration_id}")
        integration = self.db.query(Integration).filter(Integration.id == integration_id).first()
        if not integration:
            logger.warning(f"Integration with ID '{integration_id}' not found.")
            raise IntegrationNotFoundError(str(integration_id))
        return integration

    def get_integration_by_name(self, name: str) -> Integration:
        """Retrieves an Integration by its unique name."""
        logger.debug(f"Fetching integration with name: {name}")
        integration = self.db.query(Integration).filter(Integration.name == name).first()
        if not integration:
            logger.warning(f"Integration with name '{name}' not found.")
            raise IntegrationNotFoundError(name)
        return integration

    def list_integrations(self, skip: int = 0, limit: int = 100) -> List[Integration]:
        """Lists all Integrations with pagination."""
        logger.debug(f"Listing integrations (skip={skip}, limit={limit})")
        return self.db.query(Integration).offset(skip).limit(limit).all()

    def update_integration(self, integration_id: UUID, integration_data: IntegrationUpdate) -> Integration:
        """Updates an existing Integration."""
        logger.info(f"Attempting to update integration with ID: {integration_id}")
        db_integration = self.get_integration_by_id(integration_id) # Uses get_integration_by_id for existence check

        update_data = integration_data.model_dump(exclude_unset=True)
        
        # Handle API key update separately
        if "api_key" in update_data:
            db_integration.api_key_encrypted = _encrypt_api_key(update_data.pop("api_key"))
            logger.info(f"API key for integration ID {integration_id} has been updated.")

        # Update remaining fields
        for key, value in update_data.items():
            setattr(db_integration, key, value)

        try:
            self.db.commit()
            self.db.refresh(db_integration)
            logger.info(f"Integration '{db_integration.name}' updated successfully.")
            return db_integration
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Database integrity error during update: {e}")
            # Check if the error is due to a duplicate name
            if "name" in update_data:
                 raise IntegrationAlreadyExistsError(update_data["name"])
            raise IntegrationServiceError(f"Failed to update integration: {e}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during integration update: {e}")
            raise IntegrationServiceError(f"Failed to update integration: {e}")

    def delete_integration(self, integration_id: UUID) -> None:
        """Deletes an Integration and its associated logs."""
        logger.warning(f"Attempting to delete integration with ID: {integration_id}")
        db_integration = self.get_integration_by_id(integration_id) # Uses get_integration_by_id for existence check

        try:
            self.db.delete(db_integration)
            self.db.commit()
            logger.info(f"Integration ID {integration_id} deleted successfully.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during integration deletion: {e}")
            raise IntegrationServiceError(f"Failed to delete integration: {e}")

    # --- Integration Log Operations ---

    def create_integration_log(self, log_data: IntegrationLogCreate) -> IntegrationLog:
        """Creates a new Integration Log entry."""
        logger.debug(f"Logging API call for integration ID: {log_data.integration_id}")
        
        # Check if the integration exists before logging
        if not self.db.query(Integration).filter(Integration.id == log_data.integration_id).first():
            logger.warning(f"Log creation failed: Integration ID '{log_data.integration_id}' does not exist.")
            raise IntegrationNotFoundError(str(log_data.integration_id))

        db_log = IntegrationLog(
            integration_id=log_data.integration_id,
            endpoint=log_data.endpoint,
            method=log_data.method,
            status_code=log_data.status_code,
            request_body=log_data.request_body,
            response_body=log_data.response_body,
            is_success=log_data.is_success,
            error_message=log_data.error_message
        )

        try:
            self.db.add(db_log)
            self.db.commit()
            self.db.refresh(db_log)
            return db_log
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during integration log creation: {e}")
            raise IntegrationServiceError(f"Failed to create integration log: {e}")

    def list_integration_logs(self, integration_id: UUID, skip: int = 0, limit: int = 100) -> List[IntegrationLog]:
        """Lists logs for a specific Integration with pagination."""
        logger.debug(f"Listing logs for integration ID {integration_id} (skip={skip}, limit={limit})")
        
        # Check if the integration exists
        if not self.db.query(Integration).filter(Integration.id == integration_id).first():
            raise IntegrationNotFoundError(str(integration_id))

        return (
            self.db.query(IntegrationLog)
            .filter(IntegrationLog.integration_id == integration_id)
            .order_by(IntegrationLog.logged_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
