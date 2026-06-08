import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from config import settings
from models import Base

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database and creates all tables."""
    logger.info("Initializing database and creating tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete.")

@contextmanager
def get_db():
    """Dependency to get a database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Alias for the dependency function
DB_DEPENDENCY = get_db
