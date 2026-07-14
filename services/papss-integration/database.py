from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
from .models import Base

# Create the SQLAlchemy engine
# The connect_args are only needed for SQLite to allow multiple threads to access the same connection
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    """
    Initializes the database by creating all tables defined in Base.
    """
    # This will create the tables if they don't exist
    Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    """
    Dependency function to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
