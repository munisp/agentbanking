from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# --- Configuration Settings ---

class Settings:
    """
    Application settings, primarily for database connection.
    In a real application, this would use environment variables or a configuration file.
    """
    # Database URL configuration. In a production environment, this
    # would be loaded from an environment variable (e.g., os.getenv("DATABASE_URL")).
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:password@localhost:5432/tigerbeetle_db"
    )
    
    # Other settings can be added here (e.g., SECRET_KEY, API_VERSION)

# Initialize settings
settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # echo=True # Uncomment for debugging SQL queries
)

# Create a configured "Session" class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# --- Dependency for FastAPI ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Export the settings object
__all__ = ["settings", "get_db", "engine"]
