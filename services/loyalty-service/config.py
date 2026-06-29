import os
from functools import lru_cache
from typing import Generator

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables from .env file when available
if load_dotenv:
    load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./loyalty.db")
    PROJECT_NAME: str = "Loyalty Service API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = (
        "super-secret-key-for-loyalty-service"  # Should be loaded from env in production
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings. Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Database setup
settings = get_settings()

# Use check_same_thread=False for SQLite only, not needed for PostgreSQL
# For production, we assume a proper database like PostgreSQL is used.
# The `pool_pre_ping=True` helps with connection stability.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Export the settings instance
settings = get_settings()
