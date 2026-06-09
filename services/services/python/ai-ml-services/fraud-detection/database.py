from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from .models import Base
from .config import settings

# --- Synchronous Engine for initial setup (e.g., creating tables) ---
# In a real-world async application, you might only use the async engine.
# We keep the sync engine for simplicity in this example's setup.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# --- Asynchronous Engine for FastAPI application ---
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
)

# --- Asynchronous Session Maker ---
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# --- Dependency for getting an async session ---
async def get_db_session() -> AsyncSession:
    """
    Dependency function that yields an async SQLAlchemy session.
    The session is automatically closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        yield session

# --- Function to initialize the database (create tables) ---
async def init_db() -> None:
    """
    Initializes the database by creating all tables defined in Base.
    This should be called once on application startup.
    """
    async with async_engine.begin() as conn:
        # Import all models so that Base knows about them
        # This is already handled by the relative import of Base
        await conn.run_sync(Base.metadata.create_all)

# --- Custom Exception for Database Errors ---
class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass

class NotFoundError(DatabaseError):
    """Exception raised when a requested item is not found."""
    def __init__(self, model_name: str, item_id: int) -> None:
        self.model_name = model_name
        self.item_id = item_id
        super().__init__(f"{model_name} with ID {item_id} not found.")

class IntegrityError(DatabaseError):
    """Exception raised for database integrity violations (e.g., unique constraint)."""
    def __init__(self, message: str) -> None:
        super().__init__(message)