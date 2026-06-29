import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure the directory exists for the models file to be imported later
# This is a good practice for modular projects
from .models import Base 

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database settings
    DATABASE_URL: str = "sqlite:///./onboarding_service.db"
    
    # Application settings
    SERVICE_NAME: str = "onboarding-service"
    API_V1_STR: str = "/api/v1"
    
    # Logging settings (example)
    LOG_LEVEL: str = "INFO"

settings = Settings()

# --- Database Setup ---

# Use a synchronous engine for simplicity with FastAPI's dependency injection
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the database (if they don't exist)
# This should typically be handled by migration tools in a production environment, 
# but for a simple setup, this is sufficient.
def init_db():
    """Initializes the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

# --- Dependency ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize the database when the module is imported (e.g., on application startup)
# In a real application, this might be called explicitly in the main app file.
init_db()
