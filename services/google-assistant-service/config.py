import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# --- Settings ---

class Settings(BaseModel):
    """
    Application settings, loaded from environment variables.
    """
    SERVICE_NAME: str = "google-assistant-service"
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./google_assistant_service.db"
    )
    # Add other settings as needed, e.g., API keys, logging level, etc.

settings = Settings()

# --- Database Configuration ---

# Use connect_args for SQLite to allow multiple threads to access the same connection
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False # Set to True to see SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Dependency ---

def get_db() -> Generator:
    """
    Dependency function to get a database session.
    Yields a session and ensures it is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
