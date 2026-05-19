import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Database Configuration ---

# Determine the base directory for the database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use a relative path for the SQLite database file
SQLITE_DATABASE_URL = f"sqlite:///{BASE_DIR}/voice_ai_service.db"

# For production, you would typically use PostgreSQL or another robust database
# POSTGRES_DATABASE_URL = "postgresql://user:password@host:port/dbname"

# Create the SQLAlchemy engine
engine = create_engine(
    SQLITE_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Required for SQLite
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Settings Configuration ---

class Settings(BaseSettings):
    """
    Application settings class.
    Uses Pydantic's BaseSettings to load environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application metadata
    SERVICE_NAME: str = "Voice AI Service"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for managing voice AI processing jobs (e.g., transcription, synthesis)."

    # Database settings
    DATABASE_URL: str = SQLITE_DATABASE_URL
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    
    # Voice AI specific settings
    MAX_JOB_DURATION_SECONDS: int = 3600 # 1 hour
    DEFAULT_MODEL: str = "whisper-large-v3"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

# --- Dependency for Database Session ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    The session is closed automatically after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize settings for immediate use (e.g., in main.py or other modules)
settings = get_settings()
