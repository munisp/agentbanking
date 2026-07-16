import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings class. Reads environment variables for configuration.
    """
    # Database settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/etl_pipeline_db"
    
    # Service-specific settings
    SERVICE_NAME: str = "etl-pipeline"
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    Yields a session and ensures it is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example usage of environment variables for a production-ready setup:
# DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
# LOG_LEVEL=WARNING
