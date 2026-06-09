from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

# 1. Settings Class
class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables or .env file.
    """
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/unified_analytics"
    
    class Config:
        env_file = ".env"
        
settings = Settings()

# 2. Database Connection Setup
# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL
)

# Create a configured "SessionLocal" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. get_db Dependency
def get_db() -> Generator:
    """
    Dependency function to get a database session.
    Yields a session and ensures it is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
