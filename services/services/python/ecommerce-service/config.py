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

    # Database settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/ecommerce_db"
    
    # Service settings
    SERVICE_NAME: str = "ecommerce-service"
    LOG_LEVEL: str = "INFO"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings object.
    """
    return Settings()

# --- Database Setup ---

# Load settings
settings = get_settings()

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    # echo=True # Uncomment for SQL logging
)

# Create a configured "Session" class
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    Yields a session and ensures it is closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example usage of environment variable loading (optional, but good practice)
if __name__ == "__main__":
    print(f"Service Name: {settings.SERVICE_NAME}")
    print(f"Database URL (first 20 chars): {settings.DATABASE_URL[:20]}...")
