import logging
import secrets
import hashlib
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import ApiKey
from schemas import ApiKeyCreate, ApiKeyUpdate
from config import settings

# --- Custom Exceptions ---

class ServiceException(Exception):
    """Base exception for service layer errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class NotFoundException(ServiceException):
    """Raised when a resource is not found."""
    def __init__(self, resource_id: str):
        super().__init__(f"Resource with ID '{resource_id}' not found.", 404)

class ConflictException(ServiceException):
    """Raised when a resource creation or update conflicts with existing data."""
    def __init__(self, message: str):
        super().__init__(message, 409)

class InvalidCredentialsException(ServiceException):
    """Raised when an API key is invalid or inactive."""
    def __init__(self):
        super().__init__("Invalid or inactive API key.", 401)

# --- Logging Configuration ---

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Utility Functions ---

def generate_api_key(length: int = 32) -> str:
    """Generates a secure, random API key."""
    return secrets.token_urlsafe(length)

def hash_api_key(key: str) -> str:
    """Hashes the API key using SHA-256 and the application secret key as salt."""
    # Using the application secret key as a salt for a simple HMAC-like approach
    # For production, a proper KDF like Argon2 or bcrypt should be used, but for simplicity
    # and to meet the "hash the key" requirement, we use a salted SHA-256.
    salted_key = f"{settings.SECRET_KEY}:{key}".encode('utf-8')
    return hashlib.sha256(salted_key).hexdigest()

# --- Service Layer ---

class ApiKeyService:
    """
    Business logic for managing API Keys.
    """
    def __init__(self, db: Session):
        self.db = db

    def create_key(self, key_data: ApiKeyCreate) -> tuple[ApiKey, str]:
        """
        Creates a new API key, stores its hash, and returns the model and the unhashed key.
        """
        unhashed_key = generate_api_key()
        key_hash = hash_api_key(unhashed_key)
        
        db_key = ApiKey(
            key_hash=key_hash,
            owner_id=key_data.owner_id,
            name=key_data.name,
            scopes=key_data.scopes,
            expires_at=key_data.expires_at,
            metadata_json=key_data.metadata_json
        )

        try:
            self.db.add(db_key)
            self.db.commit()
            self.db.refresh(db_key)
            logger.info(f"Created new API key for owner {key_data.owner_id} with ID {db_key.id}")
            return db_key, unhashed_key
        except IntegrityError as e:
            self.db.rollback()
            if "idx_owner_name_unique" in str(e):
                raise ConflictException(f"API Key name '{key_data.name}' already exists for owner '{key_data.owner_id}'.")
            raise ServiceException(f"Database integrity error: {e}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating API key: {e}")
            raise ServiceException(f"Failed to create API key: {e}")

    def get_key_by_id(self, key_id: UUID) -> ApiKey:
        """
        Retrieves an API key by its UUID.
        """
        db_key = self.db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not db_key:
            raise NotFoundException(str(key_id))
        return db_key

    def get_keys_by_owner(self, owner_id: str, skip: int = 0, limit: int = 100) -> List[ApiKey]:
        """
        Retrieves a list of API keys for a specific owner.
        """
        return self.db.query(ApiKey).filter(ApiKey.owner_id == owner_id).offset(skip).limit(limit).all()

    def update_key(self, key_id: UUID, key_data: ApiKeyUpdate) -> ApiKey:
        """
        Updates an existing API key.
        """
        db_key = self.get_key_by_id(key_id) # Reuses NotFoundException
        
        update_data = key_data.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(db_key, key, value)

        try:
            self.db.commit()
            self.db.refresh(db_key)
            logger.info(f"Updated API key with ID {key_id}")
            return db_key
        except IntegrityError as e:
            self.db.rollback()
            if "idx_owner_name_unique" in str(e):
                # We need to get the new name from key_data, but it might be None if not updated.
                # Since we already checked ownership in the router, we can assume the name is the issue.
                # A more robust check would be to query for the conflicting name/owner combination.
                # For now, we'll use the name from the update data if present.
                conflicting_name = key_data.name if key_data.name else db_key.name
                raise ConflictException(f"API Key name '{conflicting_name}' already exists for owner '{db_key.owner_id}'.")
            raise ServiceException(f"Database integrity error: {e}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating API key {key_id}: {e}")
            raise ServiceException(f"Failed to update API key: {e}")

    def delete_key(self, key_id: UUID) -> None:
        """
        Deletes an API key by its UUID.
        """
        db_key = self.get_key_by_id(key_id) # Reuses NotFoundException
        
        try:
            self.db.delete(db_key)
            self.db.commit()
            logger.info(f"Deleted API key with ID {key_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting API key {key_id}: {e}")
            raise ServiceException(f"Failed to delete API key: {e}")

    def authenticate_key(self, api_key: str) -> ApiKey:
        """
        Authenticates an API key by hashing it and checking against the database.
        Also checks if the key is active and not expired.
        """
        key_hash = hash_api_key(api_key)
        
        db_key = self.db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        
        if not db_key:
            logger.warning("Authentication failed: Key hash not found.")
            raise InvalidCredentialsException()

        if not db_key.is_active:
            logger.warning(f"Authentication failed for key {db_key.id}: Key is inactive.")
            raise InvalidCredentialsException()

        if db_key.expires_at and db_key.expires_at < datetime.utcnow():
            logger.warning(f"Authentication failed for key {db_key.id}: Key has expired.")
            # Optionally, set is_active=False here
            raise InvalidCredentialsException()

        logger.info(f"Authentication successful for key {db_key.id} (Owner: {db_key.owner_id})")
        return db_key