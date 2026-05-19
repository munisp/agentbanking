from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

# Create the SQLAlchemy engine
# The `pool_pre_ping=True` option is useful for long-running applications
# to ensure the connection is still alive.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG # Echo SQL statements if debug is enabled
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()

# Dependency to get the database session
def get_db():
    """
    Dependency function that provides a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables (for initial setup/testing)
def init_db():
    """
    Initializes the database by creating all tables defined in Base.
    """
    # Import all models so that Base has them registered
    from . import models # noqa: F401
    Base.metadata.create_all(bind=engine)