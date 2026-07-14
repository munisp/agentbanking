import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from service import Base

DATABASE_URL = os.environ.get("VAT_DATABASE_URL", "sqlite:///./nigeria_vat.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,  # Verify connections are alive before using
    pool_size=10,  # Number of connections to maintain
    max_overflow=20,  # Additional connections allowed
    pool_timeout=30,  # Wait time for connection availability
    pool_recycle=1800,  # Recycle connections after 30 minutes
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
