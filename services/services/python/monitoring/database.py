from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
from .config import settings

# Use the database URL from the settings
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    )

# Create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()

# Dependency to get a database session
def get_db() -> None:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables (used for initial setup)
def init_db() -> None:
    # Import all models here so that Base knows them
    from . import models  # Assuming models.py will be in the same directory
    Base.metadata.create_all(bind=engine)