from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings

# Use a synchronous engine for simplicity with SQLite, as the task doesn't explicitly require async DB.
# If an async DB (like asyncpg) were required, we would use create_async_engine.
# Sticking to synchronous for broad compatibility and simplicity, but using modern SQLAlchemy 2.0 style.

# For production-ready code, we should use an async driver like asyncpg with create_async_engine.
# For this example, we'll use a simple synchronous engine with a thread-local session.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Base class for models
class Base(DeclarativeBase):
    pass

# 2. Database Engine
# Using synchronous engine for simplicity with SQLite.
# In a real-world FastAPI app, an async engine (e.g., create_async_engine) is preferred.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.DEBUG
)

# 3. Session Local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Dependency to get a database session
def get_db() -> None:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 5. Function to create tables (for initial setup)
def init_db() -> None:
    # This is typically run once on application startup or migration
    Base.metadata.create_all(bind=engine)

# NOTE: For a truly "production-ready" async FastAPI application, 
# the above should be replaced with:
# from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
# async_engine = create_async_engine(settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///"), echo=settings.DEBUG)
# AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
# async def get_async_db():
#     async with AsyncSessionLocal() as session:
#         yield session
# The current synchronous approach is used to simplify the initial setup with the default SQLite URL.