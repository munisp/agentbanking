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
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database Settings
    DATABASE_URL: str = "sqlite:///./gaming_service.db"
    
    # Service Settings
    SERVICE_NAME: str = "gaming-service"
    API_V1_STR: str = "/api/v1"
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"

@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings. Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# SQLAlchemy Engine
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True
)

# Session Local
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

# Example usage of settings (optional, for verification)
# print(f"Service Name: {settings.SERVICE_NAME}")
# print(f"Database URL: {settings.DATABASE_URL}")
