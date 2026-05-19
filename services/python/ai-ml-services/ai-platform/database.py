from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy setup
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# For SQLite, connect_args is needed for concurrent access
connect_args = {"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models (imported in models.py)
Base = declarative_base()

def get_db() -> None:
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Initializes the database and creates tables."""
    from models import Base
    logger.info("Initializing database and creating tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    # This block is for initial setup if run directly
    init_db()
