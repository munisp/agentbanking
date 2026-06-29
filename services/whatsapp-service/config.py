import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database Settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/whatsapp_db"
    
    # Service Settings
    SERVICE_NAME: str = "whatsapp-service"
    API_V1_STR: str = "/api/v1"
    
    # WhatsApp API Settings (Example)
    WHATSAPP_API_TOKEN: str = "your_whatsapp_api_token"
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v18.0"
    WHATSAPP_PHONE_ID: str = "your_phone_number_id"

settings = Settings()

# --- Database Configuration ---

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get the database session
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

# Optional: Function to create tables (for initial setup/migrations)
def create_db_and_tables():
    """
    Creates all defined tables in the database.
    This is typically used for initial setup or testing, not production.
    In production, use Alembic or similar migration tools.
    """
    from .models import Base # Import Base from models.py
    Base.metadata.create_all(bind=engine)
