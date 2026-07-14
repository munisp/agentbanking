import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://user:password@localhost/lakehouse_db")
    SERVICE_NAME: str = "lakehouse-service"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        """
        Pydantic configuration for settings.
        """
        env_file = ".env"
        env_file_encoding = "utf-8"

# Initialize settings
settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    It handles opening and closing the session automatically.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
