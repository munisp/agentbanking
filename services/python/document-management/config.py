import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration Settings ---

class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    # Use a simple SQLite database for this example. In a real app, this would be a full URL.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./document_management.db")
    SERVICE_NAME: str = "document-management"
    
    # Pagination settings
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 100

settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# --- Dependency ---

def get_db() -> Generator:
    """
    Dependency function that yields a database session.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Export for use in models.py
DB_Base = Base
