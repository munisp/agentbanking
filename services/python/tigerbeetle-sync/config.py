import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tigerbeetle_sync.db")
    
    # Service settings
    SERVICE_NAME: str = "tigerbeetle-sync"
    
    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# --- Database Setup ---

# Use connect_args for SQLite to allow multiple threads to access the same connection
# For other databases (PostgreSQL, MySQL), this is not needed.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Dependency ---

def get_db() -> Generator:
    """
    Dependency function that provides a database session.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Export settings for use in other modules
config = settings
