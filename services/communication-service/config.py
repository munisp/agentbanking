import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Define the base directory for the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database settings
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/communication_service.db"
    
    # Service settings
    SERVICE_NAME: str = "communication-service"
    LOG_LEVEL: str = "INFO"
    
    # Communication settings (placeholders for external services)
    EMAIL_API_KEY: str = "dummy_email_key"
    SMS_API_KEY: str = "dummy_sms_key"

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

# Initialize database engine and session
settings = get_settings()
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
