import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm.session import Session

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/messenger_service")
    
    # Service settings
    SERVICE_NAME: str = "messenger-service"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    """
    Get the cached settings object.
    """
    return Settings()

# --- Database Configuration ---

settings = get_settings()

# SQLAlchemy setup
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Dependency ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Configuration (Basic) ---
# In a real production environment, a more robust logging setup (e.g., using structlog)
# would be implemented, but for this task, we'll keep it simple.

import logging

# Configure basic logging
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(settings.SERVICE_NAME)

# Example usage: logger.info("Application started")
