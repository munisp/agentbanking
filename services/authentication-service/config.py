import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Settings Configuration ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./auth_service.db"
    
    # Security settings
    SECRET_KEY: str = "super-secret-key-for-development-only"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the application settings.
    """
    return Settings()

# --- Database Configuration ---

settings = get_settings()

# The engine is the starting point for SQLAlchemy. It's responsible for managing
# connections to the database.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# SessionLocal is a factory for new Session objects.
# The session is the 'staging area' for the objects loaded from the database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session for a request.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
