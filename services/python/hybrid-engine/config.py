import os
from typing import Generator

from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# --- Configuration Settings ---

class Settings(BaseModel):
    """
    Application settings loaded from environment variables.
    """
    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:password@localhost:5432/fraudstar_db"
    )
    
    # Service-specific settings
    SERVICE_NAME: str = "hybrid-engine"
    MODEL_DEFAULT_VERSION: str = "v2.1.0"
    
    class Config:
        """
        Pydantic configuration for loading from environment variables.
        """
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    # For SQLite: connect_args={"check_same_thread": False}
)

# Create a configured "Session" class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# --- Dependency ---

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Database Initialization (Optional, for initial setup) ---

# This function can be called at application startup to ensure tables exist
def init_db():
    """
    Initializes the database by creating all tables defined in models.py.
    """
    from .models import Base
    # Note: In a real application, you would use Alembic for migrations.
    # This is for simple setup/testing.
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print(f"Service Name: {settings.SERVICE_NAME}")
    print(f"Database URL: {settings.DATABASE_URL}")
    # Example of how to initialize the database if run directly
    # init_db()
