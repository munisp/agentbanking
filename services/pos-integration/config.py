import os
from typing import Generator

from pydantic import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """

    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./pos_integration.db"
    )
    
    # Service-specific settings
    SERVICE_NAME: str = "pos-integration"
    API_V1_STR: str = "/api/v1"

    class Config:
        case_sensitive = True


settings = Settings()

# SQLAlchemy setup
# Using connect_args={"check_same_thread": False} for SQLite only.
# For production PostgreSQL, this argument should be removed.
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(
    settings.DATABASE_URL, connect_args=connect_args
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
