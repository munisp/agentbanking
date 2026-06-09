import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Define the base directory for the application

class Settings(BaseSettings):
    """Application settings."""
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/translation_service")
    
    # Service settings
    SERVICE_NAME: str = "translation-service"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

# Initialize settings
settings = get_settings()

# SQLAlchemy setup
engine = create_engine(
    settings.DATABASE_URL
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    
    Yields:
        Session: A SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create the directory if it doesn't exist
os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("postgresql://postgres:postgres@localhost:5432/translation_service", "")), exist_ok=True)
