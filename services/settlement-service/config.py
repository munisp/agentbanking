import os
from functools import lru_cache
from typing import Generator

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Settings Class ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    DATABASE_URL must be a PostgreSQL connection string — SQLite is not
    supported in production due to concurrent-write limitations.
    """
    # Database settings — no default; must be set via DATABASE_URL env var
    DATABASE_URL: str

    # Service settings
    SERVICE_NAME: str = "settlement-service"
    LOG_LEVEL: str = "INFO"

    # Downstream service URLs
    PAYMENT_PROCESSING_SVC_URL: str = "http://payment-processing-service:8000"
    COMMISSION_SERVICE_URL: str = "http://commission-settlement:8080"
    SERVICE_AUTH_TOKEN: str = "commission-settlement-service"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def reject_sqlite(cls, v: str) -> str:
        if "sqlite" in v.lower():
            raise ValueError(
                "SQLite is not supported for settlement-service in production. "
                "Settlement data requires concurrent-write safe storage. "
                "Configure DATABASE_URL with a PostgreSQL connection string "
                "(e.g. postgresql://user:pass@host:5432/dbname)."
            )
        if not v.startswith(("postgresql://", "postgresql+", "postgres://")):
            raise ValueError(
                f"DATABASE_URL must be a PostgreSQL connection string. Got: {v[:30]}..."
            )
        return v

@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Raises on startup if DATABASE_URL is missing or points to SQLite.
    """
    return Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine — PostgreSQL only, no SQLite fallback
engine = create_engine(
    get_settings().DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Setup (Basic) ---

import logging

# Configure basic logging
logging.basicConfig(level=logging.getLevelName(get_settings().LOG_LEVEL))
logger = logging.getLogger(get_settings().SERVICE_NAME)

# Example usage: logger.info("Application started")
