import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings class.
    Reads environment variables for configuration.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # General Settings
    SERVICE_NAME: str = "communication-shared"
    LOG_LEVEL: str = "INFO"

    # Database Settings
    DATABASE_URL: str = "sqlite:///./communication_shared.db"
    
    # Secret Key for JWT/Security
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings instance.
    Uses lru_cache to ensure only one instance is created.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# Use check_same_thread=False for SQLite only, as it's not thread-safe by default.
# For PostgreSQL/MySQL, this parameter should be omitted.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)

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

# Create the directory if it doesn't exist (for file-based databases like SQLite)
os.makedirs(os.path.dirname(os.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)
