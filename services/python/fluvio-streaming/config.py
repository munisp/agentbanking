import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database configuration
    DATABASE_URL: str = "sqlite:///./fluvio_streaming.db"
    
    # Service configuration
    SERVICE_NAME: str = "fluvio-streaming"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# --- Database Configuration ---

# Use check_same_thread=False for SQLite in FastAPI to allow multiple threads 
# to interact with the database, which is necessary for FastAPI's default 
# dependency injection and thread pool.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Dependency ---

def get_db() -> Generator:
    """
    Dependency function to get a database session.
    It handles session creation and closing automatically.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Ensure the database directory exists if using a file-based path
if settings.DATABASE_URL.startswith("sqlite:///"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
