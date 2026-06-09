from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# Create the SQLAlchemy engine
# For other databases like PostgreSQL, this argument should be omitted
engine = create_engine(
    settings.DATABASE_URL, 
    echo=settings.ECHO_SQL,
    )

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions
Base = declarative_base()

def get_db() -> None:
    """
    Dependency function to get a database session.
    This function is used by FastAPI's Depends system.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """
    Initializes the database by creating all tables defined in Base.
    This should be called once on application startup.
    """
    # Import all models here so that they are registered with Base
    # from . import models 
    # Base.metadata.create_all(bind=engine)
    pass # Will be called from main.py or a startup script