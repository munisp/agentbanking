import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database Settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/unified_comm_db"
    
    # Service Settings
    SERVICE_NAME: str = "unified-communication-service"
    LOG_LEVEL: str = "INFO"

# Initialize settings
settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Configure the SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

# Example usage of environment variables for better security and flexibility
# if os.getenv("ENV") == "production":
#     settings.DATABASE_URL = os.getenv("PROD_DATABASE_URL")
