import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Settings:
    DATABASE_URL: str = os.getenv("RECEIPT_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
    SERVICE_PORT: int = int(os.getenv("RECEIPT_PORT", "8035"))
    SMS_API_KEY: str = os.getenv("TERMII_API_KEY", "")
    SMS_GATEWAY_URL: str = os.getenv("SMS_GATEWAY_URL", "https://api.ng.termii.com")
    WHATSAPP_API_KEY: str = os.getenv("WHATSAPP_API_KEY", "")
    WHATSAPP_API_URL: str = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v18.0")
    EMAIL_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    RECEIPT_BASE_URL: str = os.getenv("RECEIPT_BASE_URL", "https://receipts.54agent.com")
    NOTIFICATION_SERVICE_URL: str = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8010")

settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
