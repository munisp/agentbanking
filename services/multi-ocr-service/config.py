import os
from typing import Generator

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database settings
    DATABASE_URL: str = Field(
        default=os.getenv("DATABASE_URL", "sqlite:///./multi_ocr_service.db"),
        description="The database connection URL."
    )
    
    # Service specific settings
    SERVICE_NAME: str = "multi-ocr-service"
    
    # Logging settings (can be expanded)
    LOG_LEVEL: str = Field(default="INFO", description="The logging level.")

    class Config:
        env_file = ".env"
        extra = "ignore"

# Initialize settings
settings = Settings()

# SQLAlchemy setup
# For SQLite, check_same_thread is needed for concurrent requests
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    Yields a SQLAlchemy Session object and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Note: In a real production environment, the DATABASE_URL should be a secure 
# connection string for a robust database like PostgreSQL or MySQL.
# The SQLite default is for development/testing purposes.
