import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Settings:
    DATABASE_URL: str = os.getenv("NFC_QR_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
    SERVICE_PORT: int = int(os.getenv("NFC_QR_PORT", "8034"))
    QR_HMAC_SECRET: str = os.getenv("QR_HMAC_SECRET", "change-me-in-production-use-strong-secret")

settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
