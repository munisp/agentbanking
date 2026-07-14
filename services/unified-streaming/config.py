import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Determine the base directory for relative path resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    """
    Application settings for the unified-streaming service.

    Settings are loaded from environment variables or a .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./unified_streaming.db"
    ECHO_SQL: bool = False

    # Service settings
    SERVICE_NAME: str = "unified-streaming"
    LOG_LEVEL: str = "INFO"

    class Config:
        """Configuration for Pydantic settings."""
        env_file = ".env"
        env_file_encoding = "utf-8"

# Initialize settings
settings = Settings()

# Configure the database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.ECHO_SQL
)

# Configure the session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.

    Yields a SQLAlchemy Session object and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create the database file if it's SQLite and doesn't exist
if "sqlite" in settings.DATABASE_URL:
    # This is a simple way to ensure the file exists for SQLite.
    # In a real application, you would use Alembic for migrations.
    try:
        from .models import Base # Import Base for metadata
        Base.metadata.create_all(bind=engine)
    except ImportError:
        # models.py is not yet created, this will be handled later
        pass

if __name__ == "__main__":
    print(f"Service Name: {settings.SERVICE_NAME}")
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"SQL Echo: {settings.ECHO_SQL}")
