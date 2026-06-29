import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings class. Reads environment variables for configuration.
    """
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ai_orchestration.db")
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Service name
    SERVICE_NAME: str = "ai-orchestration"

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    get_settings().DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in get_settings().DATABASE_URL else {},
    pool_pre_ping=True
)

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency ---

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize settings
settings = get_settings()

# Basic logging setup (FastAPI typically handles this, but good to have a placeholder)
import logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(settings.SERVICE_NAME)
