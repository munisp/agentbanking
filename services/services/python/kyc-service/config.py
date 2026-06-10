import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Assuming models.py is in the same directory, we use relative import.
# In a real project, this might be an absolute import from the project root.
from .models import Base 

# --- Configuration Settings ---
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/kyc_service"
    
    # Service settings
    SERVICE_NAME: str = "kyc-service"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    """
    Returns a cached instance of the application settings.
    """
    return Settings()

# --- Database Setup ---
settings = get_settings()

# Create the SQLAlchemy engine

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initializes the database by creating all tables defined in Base.
    """
    # This will create tables only if they don't exist
    Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db() -> Generator[Session, None, None]:
    """
    Provides a database session for a request.
    It automatically closes the session after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize the database on startup (optional, but good for quick setup)
# In a production environment, migrations (like Alembic) would be preferred.
init_db()
