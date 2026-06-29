from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import settings
import logging

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# The DATABASE_URL is read from the settings object
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
# For SQLite, connect_args is needed for concurrent access
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency to get the database session
def get_db() -> None:
    """
    Dependency function that yields a database session.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables in the database
def init_db() -> None:
    """
    Initializes the database by creating all tables defined in the models.
    This should be called once at application startup.
    """
    from models import Base # Import Base from models.py
    logger.info("Initializing database and creating tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    # Example usage for local testing
    init_db()