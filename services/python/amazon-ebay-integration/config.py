import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# --- Configuration Settings ---

class Settings:
    """
    Application settings loaded from environment variables.
    """
    # Database settings
            DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/amazon_ebay_integration")
    
    # Other application settings can be added here
    SERVICE_NAME: str = "amazon-ebay-integration"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()

# --- Database Setup ---

# The engine is the starting point for SQLAlchemy. It's a factory for connections.
engine = create_engine(
    settings.DATABASE_URL
)

# SessionLocal is a factory for Session objects.
# We will use it to create a new session for each request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models to inherit from.
Base = declarative_base()

# --- Dependency ---

def get_db() -> Generator:
    """
    Dependency function that provides a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes the database and creates all tables."""
    # Import all models here to ensure they are registered with Base.metadata
    # In a real application, models would be imported in the main application file.
    # For this task, we assume the main application will handle table creation.
    # However, for completeness in a standalone config, we can add this.
    # Since we don't have models.py yet, we'll rely on the main app to call Base.metadata.create_all(bind=engine)
    pass

