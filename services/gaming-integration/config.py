import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load environment variables from .env file
load_dotenv()

# --- Configuration Settings ---

class Settings:
    """
    Application settings class, loaded from environment variables.
    """
    PROJECT_NAME: str = "Gaming Integration Service"
    VERSION: str = "1.0.0"
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./gaming_integration.db")
    
    # Logging settings (can be expanded)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Initialize settings
settings = Settings()

# --- Database Setup ---

# Create the SQLAlchemy engine
# For SQLite, check_same_thread is needed for FastAPI's default behavior
# For PostgreSQL/other, this parameter is ignored
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get the database session
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

# Example usage of settings (optional, but good practice)
if __name__ == "__main__":
    print(f"Project Name: {settings.PROJECT_NAME}")
    print(f"Database URL: {settings.DATABASE_URL}")
    # This block is for testing and won't run in the FastAPI application
    # It's good practice to keep it for quick checks.
    try:
        with engine.connect() as connection:
            print("Database connection successful.")
    except Exception as e:
        print(f"Database connection failed: {e}")
