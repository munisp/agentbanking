import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./voice_assistant_service.db"
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# --- Database Setup ---

# Use check_same_thread=False for SQLite only, as it's not thread-safe
# For production (PostgreSQL/MySQL), this argument should be removed.
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Dependency ---

def get_db():
    """
    Dependency function to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Optional: Print settings for verification (useful for debugging)
# print(f"Database URL: {settings.DATABASE_URL}")
# print(f"Log Level: {settings.LOG_LEVEL}")
