import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URI", os.getenv("CBN_REPORTING_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform"))
    SERVICE_PORT: int = int(os.getenv("CBN_REPORTING_PORT", "8033"))

settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
