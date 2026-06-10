import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables.
    """
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/backup_service"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions
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

def init_db():
    """Initializes the database and creates all tables."""
    Base.metadata.create_all(bind=engine)

