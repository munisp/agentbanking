from typing import Any, Dict, List, Optional, Union, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import settings
from models import Base

# Create the SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL )

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> None:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """
    Initializes the database by creating all tables.
    """
    # Import all modules here that might define models so that
    # they are registered properly on the metadata. Otherwise
    # you will have to import them first before calling init_db()
    Base.metadata.create_all(bind=engine)

# Initialize the database (create tables)
init_db()