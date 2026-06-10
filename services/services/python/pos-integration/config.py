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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pos_integration")
    
    # Service-specific settings
    SERVICE_NAME: str = "pos-integration"
    API_V1_STR: str = "/api/v1"

    class Config:
        case_sensitive = True

settings = Settings()

# SQLAlchemy setup
# For production PostgreSQL, this argument should be removed.
engine = create_engine(
    settings.DATABASE_URL
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
