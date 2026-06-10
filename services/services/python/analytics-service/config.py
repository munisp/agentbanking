import os
from typing import Generator

from pydantic import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 1. Settings Class
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Database connection string
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:password@localhost:5432/analytics_db"
    )
    
    # API settings
    SERVICE_NAME: str = "analytics-service"
    API_V1_STR: str = "/api/v1"
    
    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 100
    MAX_PAGE_SIZE: int = 1000

    class Config:
        """Pydantic configuration for settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# 2. Database Setup
# The engine is the starting point for SQLAlchemy applications.
engine = create_engine(
    settings.DATABASE_URL, 
    pool_pre_ping=True,
    # echo=True # Uncomment for debugging SQL queries
)

# SessionLocal is a factory for new Session objects.
# We will use it to create a new session for each request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is used to define the SQLAlchemy models.
# Note: In a multi-file project, this Base should ideally be imported from a central location.
# For this task, we define it here and assume models.py will import it or redefine it if necessary.
# Since models.py already defined a minimal Base, we'll keep this one for completeness of the config file.
Base = declarative_base()

# 3. Dependency to get the database session
def get_db() -> Generator:
    """
    Dependency function that provides a database session for a request.
    The session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility function to create all tables (used for initial setup/migrations)
def create_db_and_tables():
    """Creates all defined tables in the database."""
    # This import is needed to ensure models are registered with Base
    from .models import Base as ModelBase 
    ModelBase.metadata.create_all(bind=engine)
