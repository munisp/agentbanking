"""
config.py: Database configuration and dependencies for compliance-service.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Settings Configuration ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Use an in-memory SQLite database for simplicity in this example.
    # In a production environment, this would be a PostgreSQL or similar URL.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./compliance.db")
    
    # Configuration for Pydantic Settings
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# --- SQLAlchemy Setup ---

# The declarative base class for all models
Base = declarative_base()

# Create the asynchronous engine
# The connect_args are necessary for SQLite to handle concurrent access, 
# but they are generally not needed for production databases like PostgreSQL.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        settings.DATABASE_URL, 
        echo=False, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Configure the session maker
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Dependency Function ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that provides an async database session.
    It handles session creation and closing.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            # Log the exception here if a logger was configured
            print(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            # Session is closed automatically by the 'async with' block
            pass

# --- Utility for Database Initialization ---

async def init_db():
    """
    Initializes the database by creating all tables.
    """
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered with Base.metadata
        # from .models import * 
        # (In a real project, models would be imported here)
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    # This block is for testing the configuration setup
    import asyncio
    print(f"Database URL: {settings.DATABASE_URL}")
    asyncio.run(init_db())
    print("Database initialization attempt complete.")
