import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Determine the base directory for relative path resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./push_notification_service.db"
    
    # Service settings
    SERVICE_NAME: str = "push-notification-service"
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings. Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()

# Initialize settings
settings = get_settings()

# SQLAlchemy setup
# For SQLite, connect_args is needed for concurrent access
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)

# SessionLocal is the factory for new Session objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

# Example of how to import and use the base for models (will be used in models.py)
# from sqlalchemy.ext.declarative import declarative_base
# Base = declarative_base()
# NOTE: We will define Base in models.py to avoid circular imports if models.py imports config.py
# However, for a clean structure, config.py only handles connection.
# We will ensure models.py defines Base and imports engine from here if needed, or just uses the SessionLocal.
# For simplicity and standard practice, we will assume models.py will define Base and import engine for metadata.create_all.
