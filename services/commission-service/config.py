import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# --- Configuration ---
# Use environment variable for database URL, default to a local SQLite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./commission_service.db")

# --- Database Setup ---
# The connect_args is only needed for SQLite
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Dependency Injection ---
def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.

    Yields:
        Generator[Session, None, None]: A SQLAlchemy Session object.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Configuration (Optional but good practice) ---
import logging

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("commission-service")
logger.info("Configuration loaded successfully.")
