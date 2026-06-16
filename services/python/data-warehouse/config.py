from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings for the data-warehouse service.
    Uses environment variables for configuration.
    """
    # Database configuration
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/data_warehouse"
    
    # Service configuration
    SERVICE_NAME: str = "data-warehouse"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency ---

def get_db() -> Generator:
    """
    Dependency function to get a database session.
    The session is closed automatically after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
