import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings class, loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/whatsapp_order_db"
    
    # Service settings
    SERVICE_NAME: str = "whatsapp-order-service"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    A new session is created for each request and closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Configuration (Basic) ---
# In a real production environment, a more robust logging setup (e.g., using structlog)
# would be used, but for this implementation, we'll keep it simple.

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(settings.SERVICE_NAME)
