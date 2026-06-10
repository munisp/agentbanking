from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from config import settings

# Set up logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup
# The engine is the starting point for any SQLAlchemy application.
# It's an object that manages a connection pool and a dialect for talking to the database.
# We use create_async_engine for asynchronous operations.
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False, # Set to True to see all SQL queries
    future=True
)

# The SessionLocal class is a factory for new Session objects.
# We use async_sessionmaker for asynchronous sessions.
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Base class for our models
Base = declarative_base()

# Dependency to get the database session
async def get_db() -> AsyncSession:
    """
    Dependency function that provides an asynchronous database session.
    The session is automatically closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database error: {e}")
            await session.rollback()
            raise
        finally:
            # The 'async with' block handles session closing automatically, 
            # but we keep this for clarity and potential future custom logic.
            pass

# Function to create all tables (used for initial setup/testing)
async def init_db() -> None:
    """
    Initializes the database by creating all tables defined in Base.metadata.
    """
    async with engine.begin() as conn:
        # Import all models here to ensure they are registered with Base.metadata
        # In a real application, models would be imported in main.py or similar.
        # For this structure, we assume models.py will be imported elsewhere.
        # For now, we'll rely on the main application to import models.
        # await conn.run_sync(Base.metadata.create_all)
        pass

# Note: The actual table creation will be handled in main.py after models.py is defined and imported.
