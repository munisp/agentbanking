import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# --- Configuration Settings ---
class Settings:
    """
    Application settings loaded from environment variables.
    """
    # Database configuration
        DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/neural_network_service")
    # Set to False for production to prevent accidental table recreation
    ECHO_SQL: bool = os.getenv("ECHO_SQL", "False").lower() in ("true", "1", "t")

    # Service-specific settings
    SERVICE_NAME: str = "neural-network-service"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()

# --- Database Setup ---

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.ECHO_SQL,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models (imported in models.py)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    Yields a session and ensures it is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initializes the database by creating all tables defined in Base.
    This should be called once at application startup.
    """
    # Import models here to ensure they are registered with Base
    from .models import Base as ModelBase
    ModelBase.metadata.create_all(bind=engine)

# Note: In a real-world production application, table creation (init_db)
# is typically handled by a migration tool (like Alembic) and not
# called directly in the application code. For this task, we include it
# for completeness in a self-contained example.
