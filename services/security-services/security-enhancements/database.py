import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The database URL is loaded from the settings
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Create the SQLAlchemy engine
# The 'pool_pre_ping=True' setting is important for long-running applications
# to ensure the connection is still alive.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,
    echo=settings.DEBUG # Echo SQL statements if debug is true
)

# Create a configured "Session" class
# autocommit=False: transactions must be explicitly committed
# autoflush=False: changes are not flushed until commit or explicit flush
# bind=engine: binds the session to our engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db() -> Session:
    """
    Dependency to get a database session.
    It will automatically close the session after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initializes the database by creating all tables defined in Base.
    This should be called on application startup.
    """
    logger.info("Initializing database and creating tables...")
    # Import all models so that Base has them registered
    from models import Base as ModelBase
    ModelBase.metadata.create_all(bind=engine)
    logger.info("Database initialization complete.")

# Alias for the Base from models.py for external use
Base = declarative_base()