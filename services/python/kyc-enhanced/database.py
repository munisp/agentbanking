from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings

# If an async DB (like asyncpg) were required, we would use create_async_engine.

# For production-ready code, we should use an async driver like asyncpg with create_async_engine.
# For this example, we'll use a simple synchronous engine with a thread-local session.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Base class for models
class Base(DeclarativeBase):
    pass

# 2. Database Engine
# In a real-world FastAPI app, an async engine (e.g., create_async_engine) is preferred.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

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

