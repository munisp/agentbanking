from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import settings
from models import Base # Import Base from models.py

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get the database session
def get_db() -> None:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables
def init_db() -> None:
    # Base.metadata.create_all(bind=engine) is called in main.py for application startup
    pass
