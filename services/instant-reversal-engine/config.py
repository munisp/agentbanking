"""Configuration for Instant Reversal Engine."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class Settings:
    DATABASE_URL: str = os.getenv("REVERSAL_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
    SERVICE_PORT: int = int(os.getenv("REVERSAL_PORT", "8031"))
    PAYMENT_GATEWAY_URL: str = os.getenv("PAYMENT_GATEWAY_URL", "http://payment-gateway-service:8000")
    GATEWAY_API_KEY: str = os.getenv("GATEWAY_API_KEY", "")
    NOTIFICATION_SERVICE_URL: str = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")


settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
