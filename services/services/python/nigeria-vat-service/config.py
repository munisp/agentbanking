import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .service import Base

DATABASE_URL = os.environ.get("VAT_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nigeria_vat_service")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
