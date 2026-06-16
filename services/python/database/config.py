import os
from pathlib import Path
from typing import Generator

from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Define the base directory for the application
BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseModel):
    """
    Application settings configuration.
    Uses environment variables for production-ready deployment.
    """
    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://postgres:postgres@localhost:5432/database"      )
    
    # Other service-specific settings can be added here
    SERVICE_NAME: str = "database"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Initialize settings
settings = Settings()

# SQLAlchemy Engine and SessionLocal setup
# The engine is the starting point for SQLAlchemy
engine = create_engine(
    settings.DATABASE_URL
)

# SessionLocal is a factory for new Session objects
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    This is used by FastAPI endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example of how to use the settings in a production environment
# print(f"Connecting to database at: {settings.DATABASE_URL}")
