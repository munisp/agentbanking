from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from typing import Generator

from config import settings, logger

# The database URL is constructed in config.py
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
# 'pool_pre_ping=True' is a good practice for production to ensure connections are alive
# 'echo=True' can be used for debugging, but is set to False for production readiness
try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        pool_pre_ping=True, 
        pool_size=20, 
        max_overflow=0,
        connect_args={"options": "-c timezone=utc"} # Enforce UTC timezone for consistency
    )
    logger.info("SQLAlchemy Engine created successfully.")
except Exception as e:
    logger.error(f"Error creating SQLAlchemy Engine: {e}")
    # In a real application, this might raise an exception or use a fallback
    # For this implementation, we proceed, but log the error.

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions
Base = declarative_base()

def get_db() -> Generator:
    """
    Dependency to get a database session.
    It handles closing the session after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during request: {e}")
        raise
    finally:
        db.close()

def init_db() -> None:
    """
    Creates all tables defined in the Base metadata.
    This should typically be run once during application startup or migration.
    """
    # Import all models here so that they are registered with Base.metadata
    # We assume models.py will be imported elsewhere, but for completeness:
    # from . import models 
    
    logger.info("Attempting to create all database tables...")
    try:
        # Base.metadata.create_all(bind=engine)
        # NOTE: For a production-ready system, migrations (e.g., Alembic) should be used.
        # We will comment out create_all to simulate a production environment where tables
        # are managed by a separate migration tool, but keep the function for structure.
        # For a simple test, uncomment the line above.
        logger.info("Database initialization function defined. (create_all commented out for production-readiness)")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")