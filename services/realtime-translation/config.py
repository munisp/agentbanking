import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .service import Base

DATABASE_URL = os.environ.get("TRANSLATION_DATABASE_URL", "sqlite:///./translation.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
