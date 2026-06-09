import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration ---
# In a real-world application, this would be loaded from environment variables or a settings file
# PostgreSQL database configuration.
# The `models.py` uses PG_UUID, so we assume a PostgreSQL backend.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost/reporting_engine_db"
)

# --- Database Engine and Session Setup ---
# and assume a proper setup. `pool_pre_ping=True` is good for production stability.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# SessionLocal is the factory for new Session objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency Injection ---
def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Utility for creating tables (for initial setup) ---
def create_db_and_tables():
    """
    Creates all tables defined in the Base metadata.
    This should typically be run once during application startup or migration.
    """
    from .models import Base
    Base.metadata.create_all(bind=engine)
