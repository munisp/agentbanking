import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database Settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/compliance_db"
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "compliance-workflows"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# Use a separate engine for the application
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# SessionLocal is the factory for creating new Session objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
