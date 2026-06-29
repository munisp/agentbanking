import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database configuration
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/workflow_db"
    
    # Service configuration
    SERVICE_NAME: str = "workflow-orchestration"
    API_V1_STR: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings. Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()

settings = get_settings()

# --- Database Setup ---

# The engine is created using the configured DATABASE_URL.
# 'pool_pre_ping=True' is used to ensure connections are alive.
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    # For production, consider removing 'echo=True'
    # echo=True 
)

# SessionLocal is a factory for new Session objects.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency Injection ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    A new session is created for each request and closed afterwards.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example usage of settings (optional, for verification/logging)
# print(f"Service: {settings.SERVICE_NAME}")
# print(f"Database URL (partial): {settings.DATABASE_URL.split('@')[-1]}")
