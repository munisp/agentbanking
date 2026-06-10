import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm.session import Session

# ----------------------------------------------------------------------
# Configuration Settings
# ----------------------------------------------------------------------

class Settings:
    """
    Application settings class. Reads configuration from environment variables.
    """
    # Database settings
        # but the structure is ready for a production PostgreSQL/MySQL connection.
    # In a real-world scenario, this would be read from a .env file or environment variables.
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/snapchat_service"
    )
    
    # API settings
    PROJECT_NAME: str = "Snapchat Service API"
    VERSION: str = "1.0.0"
    
    # Logging settings can be added here
    
settings = Settings()

# ----------------------------------------------------------------------
# Database Setup
# ----------------------------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ----------------------------------------------------------------------
# Dependency
# ----------------------------------------------------------------------

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

# ----------------------------------------------------------------------
# Logging Setup
# ----------------------------------------------------------------------
# import logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
