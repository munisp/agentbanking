import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Settings Class ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    
    Uses pydantic_settings to manage configuration, prioritizing environment 
    variables and falling back to defaults or a .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database settings
    # Example URL: postgresql+psycopg2://user:password@localhost:5432/document_processing_db
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/document_processing_db"
    
    # Application settings
    SERVICE_NAME: str = "document-processing"
    API_V1_STR: str = "/api/v1"
    
    # Logging settings (simplified)
    LOG_LEVEL: str = "INFO"

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

settings = get_settings()

# --- Database Configuration ---

# The engine is created using the configured DATABASE_URL.
# The 'pool_pre_ping=True' is a common setting for long-running applications 
# to ensure connections are still alive.
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    echo=False # Set to True to see all SQL queries
)

# SessionLocal is a factory for new Session objects.
# 'autocommit=False' and 'autoflush=False' are standard for a unit of work pattern.
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    
    The session is automatically closed after the request is finished, 
    even if an error occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
