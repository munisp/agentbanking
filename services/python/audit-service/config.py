import os
from typing import Generator

from pydantic import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # General Service Settings
    SERVICE_NAME: str = "audit-service"
    
    # Database Settings
        # In a production environment, this would be a PostgreSQL or similar connection string.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/audit_service")
    
    # Export Settings
    EXPORT_STORAGE_PATH: str = os.getenv("EXPORT_STORAGE_PATH", "/tmp/audit_exports")
    
    class Config:
        """Pydantic configuration for environment variables."""
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
# For production databases like PostgreSQL, this is not required.
engine = create_engine(
    settings.DATABASE_URL
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency Injection ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    It yields the session and ensures it is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Ensure the export directory exists
os.makedirs(settings.EXPORT_STORAGE_PATH, exist_ok=True)
