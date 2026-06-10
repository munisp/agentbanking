import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Settings:
    DATABASE_URL: str = os.getenv("WALLET_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
    SERVICE_PORT: int = int(os.getenv("WALLET_PORT", "8032"))

settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
