import logging
from typing import List, Optional, Type, TypeVar
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from models import User, Party, LandAsset, Agreement
from schemas import (
    UserCreate, UserUpdate, PartyCreate, PartyUpdate, LandAssetCreate, LandAssetUpdate,
    AgreementCreate, AgreementUpdate
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Custom Exceptions ---

class NotFoundException(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class DuplicateEntryException(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class AuthenticationException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- Utility Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

# --- Base Service Class ---

ModelType = TypeVar("ModelType", bound=Type[object])
CreateSchemaType = TypeVar("CreateSchemaType", bound=Type[object])
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=Type[object])

class BaseService:
    """Base class for CRUD operations."""
    def __init__(self, model: ModelType) -> None:
        self.model = model
        self.model_name = model.__name__

    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """Retrieve a single object by ID."""
        logger.info(f"Fetching {self.model_name} with ID: {id}")
        result = await db.execute(select(self.model).where(self.model.id == id))
        obj = result.scalars().first()
        if not obj:
            logger.warning(f"{self.model_name} with ID {id} not found.")
            raise NotFoundException(detail=f"{self.model_name} not found")
        return obj

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Retrieve multiple objects."""
        logger.info(f"Fetching multiple {self.model_name} (skip: {skip}, limit: {limit})")
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj_in: CreateSchemaType) -> ModelType:
        """Create a new object."""
        try:
            obj_data = obj_in.model_dump()
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            logger.info(f"Created new {self.model_name} with ID: {db_obj.id}")
            return db_obj
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Integrity error during {self.model_name} creation: {e}")
            raise DuplicateEntryException(detail=f"A {self.model_name} with this unique field already exists.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating {self.model_name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not create {self.model_name}")

    async def update(self, db: AsyncSession, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        """Update an existing object."""
        try:
            update_data = obj_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_obj, field, value)
            
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            logger.info(f"Updated {self.model_name} with ID: {db_obj.id}")
            return db_obj
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Integrity error during {self.model_name} update: {e}")
            raise DuplicateEntryException(detail=f"A {self.model_name} with this unique field already exists.")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating {self.model_name}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not update {self.model_name}")

    async def remove(self, db: AsyncSession, id: int) -> ModelType:
        """Delete an object by ID."""
        db_obj = await self.get(db, id) # Reuses get for existence check and 404
        
        await db.delete(db_obj)
        await db.commit()
        logger.info(f"Removed {self.model_name} with ID: {id}")
        return db_obj

# --- Specific Services ---

class UserService(BaseService):
    def __init__(self) -> None:
        super().__init__(User)

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """Retrieve a user by email."""
        logger.info(f"Fetching User by email: {email}")
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def create_user(self, db: AsyncSession, user_in: UserCreate) -> User:
        """Create a new user with a hashed password."""
        if await self.get_by_email(db, user_in.email):
            raise DuplicateEntryException(detail="User with this email already exists")
            
        hashed_password = get_password_hash(user_in.password)
        user_data = user_in.model_dump(exclude={"password"})
        db_user = User(**user_data, hashed_password=hashed_password)
        
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        logger.info(f"Created new User with ID: {db_user.id}")
        return db_user

    async def authenticate_user(self, db: AsyncSession, email: str, password: str) -> Optional[User]:
        """Authenticates a user by email and password."""
        user = await self.get_by_email(db, email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

class PartyService(BaseService):
    def __init__(self) -> None:
        super().__init__(Party)

class LandAssetService(BaseService):
    def __init__(self) -> None:
        super().__init__(LandAsset)

    async def get_by_parcel_id(self, db: AsyncSession, parcel_id: str) -> Optional[LandAsset]:
        """Retrieve a land asset by its unique parcel ID."""
        logger.info(f"Fetching LandAsset by parcel_id: {parcel_id}")
        result = await db.execute(select(LandAsset).where(LandAsset.parcel_id == parcel_id))
        return result.scalars().first()

    async def create(self, db: AsyncSession, obj_in: LandAssetCreate) -> LandAsset:
        """Custom create to check for owner existence and parcel ID duplication."""
        # Check if owner exists
        try:
            await PartyService().get(db, obj_in.owner_id)
        except NotFoundException:
            raise NotFoundException(detail=f"Owner Party with ID {obj_in.owner_id} not found.")

        # Check for duplicate parcel_id
        if await self.get_by_parcel_id(db, obj_in.parcel_id):
            raise DuplicateEntryException(detail=f"LandAsset with parcel_id '{obj_in.parcel_id}' already exists.")

        return await super().create(db, obj_in)

class AgreementService(BaseService):
    def __init__(self) -> None:
        super().__init__(Agreement)

    async def create(self, db: AsyncSession, obj_in: AgreementCreate) -> Agreement:
        """Custom create to check for LandAsset and Party existence."""
        # Check if LandAsset exists
        try:
            await LandAssetService().get(db, obj_in.land_asset_id)
        except NotFoundException:
            raise NotFoundException(detail=f"LandAsset with ID {obj_in.land_asset_id} not found.")

        # Check if Party exists
        try:
            await PartyService().get(db, obj_in.party_id)
        except NotFoundException:
            raise NotFoundException(detail=f"Party with ID {obj_in.party_id} not found.")

        return await super().create(db, obj_in)

# Instantiate services
user_service = UserService()
party_service = PartyService()
land_asset_service = LandAssetService()
agreement_service = AgreementService()
