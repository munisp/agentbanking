import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the asynchronous engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG, # Echo SQL statements for debugging
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

# Create a configured "Session" class
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # Prevents objects from expiring after commit
)

async def init_db() -> None:
    """Initializes the database by creating all tables."""
    logger.info("Initializing database...")
    async with engine.begin() as conn:
        # Drop and re-create tables for a clean start (for development/testing)
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialization complete.")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

# Alias for dependency injection
DBSession = get_db