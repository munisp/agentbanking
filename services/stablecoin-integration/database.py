from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from config import settings
# Import all models to ensure they are registered with the Base metadata
from models import Base

# Use the synchronous database URL for the engine
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
    echo=settings.DEBUG
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """
    Initializes the database by creating all tables.
    """
    # This will create the tables if they don't exist
    Base.metadata.create_all(bind=engine)

if settings.DEBUG:
    # Initialize the database when the module is imported in debug mode
    init_db()