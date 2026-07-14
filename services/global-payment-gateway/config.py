import os
from functools import lru_cache
from typing import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm.session import Session

# --- Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./global_payment_gateway.db"
    
    # Service settings
    SERVICE_NAME: str = "global-payment-gateway"
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached instance of the application settings.
    """
    return Settings()

# --- Database Configuration ---

settings = get_settings()

# SQLAlchemy setup
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions
Base = declarative_base()

# --- Dependency ---

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

# --- Utility for initial database creation ---

def create_db_and_tables():
    """
    Creates the database and all defined tables.
    This should be called once on application startup.
    """
    # Import all models here so that they are registered with Base.metadata
    # from . import models 
    Base.metadata.create_all(bind=engine)
