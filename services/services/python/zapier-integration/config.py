import os
from functools import lru_cache
from typing import Generator

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core settings
    PROJECT_NAME: str = "Zapier Integration Service"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/zapier_integration"      )
    ECHO_SQL: bool = os.getenv("ECHO_SQL", "False").lower() in ("true", "1", "t")

@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings instance. Uses lru_cache to ensure a single instance.
    """
    return Settings()

# Initialize settings
settings = get_settings()

# SQLAlchemy setup
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.ECHO_SQL
)

# SessionLocal is a factory for new Session objects
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Example usage of settings (optional, but good for verification)
if settings.DEBUG:
    print(f"Project Name: {settings.PROJECT_NAME}")
    print(f"Database URL: {settings.DATABASE_URL}")
