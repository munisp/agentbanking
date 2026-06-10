import logging
import uuid
from typing import List, Optional, Type, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models, schemas
from .config import settings

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class NotFoundException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class ConflictException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class AuthenticationException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- Security Utilities (Placeholders) ---

# NOTE: In a real application, these would be implemented using libraries like passlib and python-jose
def get_password_hash(password: str) -> str:
    """Placeholder for password hashing."""
    # Using a simple placeholder for demonstration. Replace with proper hashing (e.g., bcrypt)
    return f"hashed_{password}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Placeholder for password verification."""
    # Using a simple placeholder for demonstration. Replace with proper verification
    return get_password_hash(plain_password) == hashed_password

def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """Placeholder for JWT token creation."""
    # Using a simple placeholder. Replace with proper JWT encoding
    return f"fake_jwt_token_for_{data.get('sub')}"

# --- Generic Service Class ---

ModelType = TypeVar("ModelType", bound=models.Base)
SchemaType = TypeVar("SchemaType", bound=schemas.BaseSchema)

class BaseService:
    def __init__(self, model: Type[ModelType]):
        self.model = model
        self.name = model.__name__

    def get(self, db: Session, id: uuid.UUID) -> ModelType:
        """Retrieve a single item by ID."""
        item = db.query(self.model).filter(self.model.id == id).first()
        if not item:
            logger.warning(f"{self.name} with ID {id} not found.")
            raise NotFoundException(detail=f"{self.name} not found")
        return item

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Retrieve multiple items."""
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: SchemaType, owner_id: uuid.UUID) -> ModelType:
        """Create a new item."""
        try:
            db_obj = self.model(**obj_in.model_dump(), owner_id=owner_id)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            logger.info(f"Created new {self.name} with ID {db_obj.id}")
            return db_obj
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating {self.name}: {e}")
            raise ConflictException(detail=f"A {self.name} with the provided unique fields already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating {self.name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not create {self.name}")

    def update(self, db: Session, db_obj: ModelType, obj_in: SchemaType) -> ModelType:
        """Update an existing item."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            logger.info(f"Updated {self.name} with ID {db_obj.id}")
            return db_obj
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error updating {self.name}: {e}")
            raise ConflictException(detail=f"A {self.name} with the provided unique fields already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating {self.name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not update {self.name}")

    def remove(self, db: Session, id: uuid.UUID) -> ModelType:
        """Delete an item by ID."""
        db_obj = self.get(db, id) # Use get to ensure it exists and raise 404 if not
        db.delete(db_obj)
        db.commit()
        logger.info(f"Removed {self.name} with ID {id}")
        return db_obj

# --- Specific Service Implementations ---

class UserService(BaseService):
    def __init__(self):
        super().__init__(models.User)

    def create_user(self, db: Session, user_in: schemas.UserCreate) -> models.User:
        """Create a new user with a hashed password."""
        hashed_password = get_password_hash(user_in.password)
        db_user = models.User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=hashed_password,
        )
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            logger.info(f"Created new User with ID {db_user.id}")
            return db_user
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating User: {e}")
            raise ConflictException(detail="User with this email or username already exists.")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating User: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create User")

    def get_by_email(self, db: Session, email: str) -> Optional[models.User]:
        """Retrieve a user by email."""
        return db.query(models.User).filter(models.User.email == email).first()

    def get_by_username(self, db: Session, username: str) -> Optional[models.User]:
        """Retrieve a user by username."""
        return db.query(models.User).filter(models.User.username == username).first()

class DatasetService(BaseService):
    def __init__(self):
        super().__init__(models.Dataset)

class ExperimentService(BaseService):
    def __init__(self):
        super().__init__(models.Experiment)

class ModelService(BaseService):
    def __init__(self):
        super().__init__(models.Model)

# --- Authentication Service ---

class AuthService:
    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[models.User]:
        """Authenticate a user by username and password."""
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    def create_token_for_user(self, user: models.User) -> str:
        """Create an access token for a given user."""
        access_token_expires = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        to_encode = {"sub": str(user.id)}
        return create_access_token(to_encode, expires_delta=access_token_expires)

# --- Service Instances ---

user_service = UserService()
dataset_service = DatasetService()
experiment_service = ExperimentService()
model_service = ModelService()
auth_service = AuthService()