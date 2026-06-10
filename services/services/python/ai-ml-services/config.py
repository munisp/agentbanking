import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Settings Configuration ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_ml_services"
    
    # Service-specific settings
    SERVICE_NAME: str = "ai-ml-services"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# --- Database Configuration ---

# this would be a PostgreSQL or similar connection.
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# The engine is the starting point for SQLAlchemy. It's responsible for 
# communicating with the database.
engine = create_engine(
)

# SessionLocal is a factory for new Session objects. 
# We will use it to create a new session for each request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions.
Base = declarative_base()

# --- Dependency for Database Session ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example usage of settings (optional, but good practice)
if settings.LOG_LEVEL == "DEBUG":
    print(f"Database URL: {settings.DATABASE_URL}")
