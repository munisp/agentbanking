"""
Configuration settings and database utilities for the rule-engine service.
"""
import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./rule_engine.db"
    
    # Service settings
    SERVICE_NAME: str = "rule-engine"
    LOG_LEVEL: str = "INFO"

    class Config:
        """Pydantic configuration for settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# --- Database Setup ---

# Use a relative path for SQLite for simplicity in the sandbox, but the structure
# supports any SQLAlchemy-compatible database via DATABASE_URL.
# For SQLite, check_same_thread is needed for FastAPI/SQLAlchemy integration.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    This handles opening and closing the session automatically.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility function to create all tables (used for initial setup)
def create_db_and_tables():
    """Creates all database tables defined in Base metadata."""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Example usage: create the database file if it doesn't exist
    print(f"Creating database and tables at: {settings.DATABASE_URL}")
    create_db_and_tables()
    print("Database setup complete.")
