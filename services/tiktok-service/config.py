from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

class Settings(BaseSettings):
    """
    Application settings for the tiktok-service.
    Uses Pydantic BaseSettings to load environment variables.
    """
    DATABASE_URL: str = "sqlite:///./tiktok_service.db"
    SERVICE_NAME: str = "tiktok-service"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

# Initialize settings
settings = Settings()

# SQLAlchemy setup
# The engine is the starting point for SQLAlchemy. It's a factory for connections.
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)

# SessionLocal is a factory for Session objects.
# Each instance of SessionLocal will be a database session.
# The 'autocommit' is set to False to prevent the session from committing
# automatically after every operation. 'autoflush' is set to False to prevent
# the session from flushing automatically when a query is executed.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative class definitions
Base = declarative_base()

def get_db():
    """
    Dependency function to get a database session.
    This is used by FastAPI's Depends system.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
