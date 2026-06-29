import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost/workflow_db"
    
    # Service
    SERVICE_NAME: str = "workflow-service"
    LOG_LEVEL: str = "INFO"

@lru_cache
def get_settings() -> Settings:
    """
    Get the application settings. Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    # For SQLite, check_same_thread=False is needed. For PostgreSQL, this is usually not needed.
    # We assume PostgreSQL for production-ready code.
)

# Create a configured "Session" class
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    
    Yields:
        Generator[Session, None, None]: A SQLAlchemy Session object.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Optional: Initialize logging (basic setup)
import logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(settings.SERVICE_NAME)
