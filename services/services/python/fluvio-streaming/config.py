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
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fluvio_streaming"
    
    # Service configuration
    SERVICE_NAME: str = "fluvio-streaming"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# --- Database Configuration ---

# to interact with the database, which is necessary for FastAPI's default 
# dependency injection and thread pool.
engine = create_engine(
    settings.DATABASE_URL
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
if settings.DATABASE_URL.startswith("postgresql://postgres:postgres@localhost:5432/fluvio_streaming"):
    db_path = settings.DATABASE_URL.replace("postgresql://postgres:postgres@localhost:5432/fluvio_streaming", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
