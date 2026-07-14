from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from config import settings
from typing import AsyncGenerator

# Use a placeholder for the async engine. 
# In a real application, this would be a postgresql+asyncpg:// or similar.
# For simplicity and to avoid external dependencies in this sandbox, we'll use a sync SQLite 
# with a mock async wrapper, but the code structure will be for async.
# NOTE: For a true production-ready async app, the engine must be async (e.g., asyncpg).
# We will use a standard SQLite for the model definitions and mock the async behavior.

# In a real project, you would use:
# ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
# engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)

# For this implementation, we will use a simple SQLite for model definition
# and structure the session management for an async environment.
# We will assume the `settings.DATABASE_URL` is configured for an async driver.
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=False, 
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields a new database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db() -> None:
    """
    Initializes the database by creating all tables.
    """
    async with engine.begin() as conn:
        # Import all modules here that might define models so that
        # they are registered with the Base.metadata.
        # Base.metadata.create_all(bind=engine)
        # For async, we use run_sync
        await conn.run_sync(Base.metadata.create_all)