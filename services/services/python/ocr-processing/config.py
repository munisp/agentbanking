import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# 1. Settings Class
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/ocr_db"
    
    # Service-specific settings
    OCR_ENGINE_URL: str = "http://ocr-engine-service:8001/api/v1/process"
    OCR_TIMEOUT_SECONDS: int = 60

@lru_cache()
def get_settings():
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

# 2. Database Connection Setup
settings = get_settings()

# Use a standard engine for the database connection
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
        # 
)

# Configure a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. get_db Dependency
def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
