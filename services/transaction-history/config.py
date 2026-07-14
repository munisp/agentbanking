import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./transaction_history.db"
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# --- Database Configuration ---

# SQLAlchemy Engine
# The connect_args are only needed for SQLite to allow multiple threads to access the same connection.
# For production databases like PostgreSQL, this should be removed.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Configuration ---

import logging

# Configure basic logging
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger("transaction-history-service")
logger.setLevel(settings.LOG_LEVEL.upper())

# Example usage: logger.info("Service started successfully.")
