from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from config import settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Database setup
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# For other databases (PostgreSQL, MySQL), this parameter is not needed.

engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> None:
    """
    Dependency to get a database session.
    This will be used in FastAPI's dependency injection system.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """
    Initializes the database by creating all tables defined in models.py.
    """
    from models import Base as ModelBase # Import Base from models.py
    ModelBase.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully.")

# The Base object from models.py is used for table creation,
# but we need to ensure it's the same Base object.
# Since we are using declarative_base() in models.py, we need to import it there.
# We will assume that models.py is imported elsewhere to register the models.