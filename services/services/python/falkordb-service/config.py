import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database Settings
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost/falkordb_service_db"
    
    # Service Settings
    SERVICE_NAME: str = "falkordb-service"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "super-secret-key" # Should be generated and stored securely in production

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    return Settings()

# --- Database Setup ---

settings = get_settings()

# The engine is the starting point for any SQLAlchemy application.
# It's responsible for managing connections to the database.
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    # echo=True # Uncomment for debugging SQL queries
)

# SessionLocal is a factory for new Session objects.
# It is configured to be thread-local (scoped_session is often used for this in web apps, 
# but for FastAPI dependency, a simple factory is sufficient).
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
