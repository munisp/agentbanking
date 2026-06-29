import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./unified_communication_hub.db"
    
    # Service settings
    SERVICE_NAME: str = "unified-communication-hub"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# Use connect_args for SQLite to allow multiple threads to access the same connection
# For production use with PostgreSQL/MySQL, this should be removed.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)

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

# --- Logging Setup (Basic) ---
# In a real production app, a more robust logging setup (e.g., using structlog)
# would be used, but for this task, a basic setup is sufficient.
import logging

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(settings.SERVICE_NAME)
