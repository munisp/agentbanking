from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings
import logging

log = logging.getLogger(__name__)

# SQLAlchemy setup for asynchronous operations
# We use 'asyncpg' driver for PostgreSQL
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql+asyncpg")

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False, # Set to True to see SQL queries for debugging
    pool_size=20, # Connection pool size
    max_overflow=0, # Max connections beyond pool_size
)

# Configure the session maker
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    """Base class which provides automated table name
    and other common features for SQLAlchemy models."""
    pass

# Dependency to get a database session
async def get_db() -> AsyncSession:
    """
    Dependency function that yields a new database session.
    The session is automatically closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            log.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

log.info("Database engine and session maker initialized.")