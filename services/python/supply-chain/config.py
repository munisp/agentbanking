import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Configuration Settings ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/supply_chain"
    
    # Service-specific settings
    SERVICE_NAME: str = "supply-chain"
    API_V1_STR: str = "/api/v1"

settings = Settings()

# --- Database Setup ---

engine = create_engine(
    settings.DATABASE_URL
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

# Create the database file if it doesn't exist and create tables
def init_db():
    """
    Initializes the database and creates all tables defined in Base.
    This should be called before the application starts.
    """
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Simple test to ensure the setup works
    print(f"Service Name: {settings.SERVICE_NAME}")
    print(f"Database URL: {settings.DATABASE_URL}")
    init_db()
    print("Database initialized (supply_chain.db created if it didn't exist).")
