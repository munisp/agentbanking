import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Settings Class ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./settlement_service.db"
    
    # Service settings
    SERVICE_NAME: str = "settlement-service"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    """
    return Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    get_settings().DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in get_settings().DATABASE_URL else {}
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Setup (Basic) ---

import logging

# Configure basic logging
logging.basicConfig(level=logging.getLevelName(get_settings().LOG_LEVEL))
logger = logging.getLogger(get_settings().SERVICE_NAME)

# Example usage: logger.info("Application started")
