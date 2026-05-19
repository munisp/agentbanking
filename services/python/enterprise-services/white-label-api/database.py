from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
from .models import Base # Import Base from models to ensure models are registered

# Create the SQLAlchemy engine
# The `connect_args` is for SQLite only, to allow multiple threads to access the database
# For production databases like PostgreSQL, this should be removed.
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(settings.DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database and creates all tables."""
    # This is for development/testing. In production, migrations (like Alembic) should be used.
    Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()