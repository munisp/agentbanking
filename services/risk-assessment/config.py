import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Determine the base directory for relative paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        DATABASE_URL (str): The SQLAlchemy database connection URL.
    """
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/risk_assessment.db"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings. Uses lru_cache to ensure settings are loaded only once.
    
    Returns:
        Settings: The application settings instance.
    """
    return Settings()

# Initialize settings
settings = get_settings()

# SQLAlchemy setup
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    
    Yields:
        Session: A SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Ensure the database directory exists if using SQLite
if "sqlite" in settings.DATABASE_URL:
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
