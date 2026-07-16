from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup
SQLALCHEMY_DATABASE_URL = settings.SQLALCHEMY_DATABASE_URL

try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        # connect_args={"check_same_thread": False} # Only for SQLite
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("Database engine and session factory initialized.")
except Exception as e:
    logger.error(f"Failed to initialize database components: {e}")
    raise

def get_db():
    """
    Dependency to get a database session.
    Yields a session and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during transaction: {e}")
        raise
    finally:
        db.close()
        logger.debug("Database session closed.")

def init_db():
    """
    Initializes the database by creating all tables.
    Should be called on application startup.
    """
    logger.info("Attempting to create database tables...")
    # Import all models here so that they are registered with Base.metadata
    from . import models
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully (if they didn't exist).")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        # In a real application, you might want to exit or retry here
