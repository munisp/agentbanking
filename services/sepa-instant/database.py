from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from config import settings
from models import Base

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency ---

def get_db() -> None:
    """
    Dependency function to get a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error during request: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# --- Initialization ---

def init_db() -> None:
    """
    Initializes the database by creating all tables defined in Base.
    """
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        # In a real application, you might want to exit or retry here
        raise