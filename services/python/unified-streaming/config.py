import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Determine the base directory for relative path resolution

class Settings(BaseSettings):
    """
    Application settings for the unified-streaming service.

    Settings are loaded from environment variables or a .env file.
    """
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/unified_streaming"
    ECHO_SQL: bool = False

    # Service settings
    SERVICE_NAME: str = "unified-streaming"
    LOG_LEVEL: str = "INFO"

    class Config:
        """Configuration for Pydantic settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"

# Initialize settings
settings = Settings()

# Configure the database engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.ECHO_SQL
)

# Configure the session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.

    Yields a SQLAlchemy Session object and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

