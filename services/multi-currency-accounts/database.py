from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Generator

from config import settings

# Use synchronous engine for simplicity in this example, but structure for async is common
# For a real production app, an async driver (e.g., asyncpg) and AsyncEngine/AsyncSession should be used.
# We will use a synchronous engine with a thread-local session for simplicity.

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# The engine is the starting point for any SQLAlchemy application.
# It's a factory for connections.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
    pool_pre_ping=True
)

# SessionLocal is a factory for Session objects.
# We will use it to create a new session for each request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()

def get_db() -> Generator:
    """
    Dependency function that yields a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables in the database
def create_db_and_tables() -> None:
    """
    Creates all tables defined in Base.metadata.
    """
    Base.metadata.create_all(bind=engine)