from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from config import settings
import logging

logger = logging.getLogger(settings.APP_NAME)

# Create the database engine
# The `pool_pre_ping=True` setting is used to ensure connections are alive
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    echo=settings.DEBUG # Echo SQL statements if debug is true
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db() -> Session:
    """
    Dependency to get a database session.
    This function is a generator that yields a database session and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def init_db() -> None:
    """
    Initializes the database and creates all tables defined in models.py.
    This should be called once on application startup.
    """
    try:
        # Import all models so that Base has them registered
        from models import Base as ModelBase
        ModelBase.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        # In a production environment, you might want to raise the exception
        # or implement a retry mechanism.
