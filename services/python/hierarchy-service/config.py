import os
from typing import Generator

from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Determine the base directory for the application

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database Settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/hierarchy_service")
    ECHO_SQL: bool = False  # Set to True to see all SQL queries

    # Service Metadata
    SERVICE_NAME: str = "Hierarchy Service"
    SERVICE_VERSION: str = "1.0.0"
    
    # Other settings can be added here (e.g., logging level, external service URLs)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Initialize settings
settings = Settings()

# SQLAlchemy Engine
# which is common in FastAPI/Uvicorn environments.
engine = create_engine(
    settings.DATABASE_URL, 
    echo=settings.ECHO_SQL
)

# SessionLocal class for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    This session is automatically closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import Base from models to ensure models are registered with the engine
# This is typically done in a main application file, but for a standalone config, 
# we can ensure the tables are created here for simplicity in a microservice context.
from .models import Base

def init_db():
    """
    Creates all database tables defined in models.py.
    """
    # This should be called once on application startup
    Base.metadata.create_all(bind=engine)

# Note: In a real production environment, database migrations (e.g., Alembic) 
# would be used instead of Base.metadata.create_all().
