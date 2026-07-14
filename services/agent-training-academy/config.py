import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class Settings:
    DATABASE_URL: str = os.getenv("TRAINING_DATABASE_URL", "postgresql://doadmin:AVNS_MSy6CW3EGXnA8wJgkLv@db-postgresql-nyc1-18193-do-user-10555812-0.e.db.ondigitalocean.com:25060/link_core_banking")
    SERVICE_PORT: int = int(os.getenv("TRAINING_PORT", "8001"))
    NOTIFICATION_SERVICE_URL: str = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8010")
    CERTIFICATE_STORAGE_URL: str = os.getenv("CERTIFICATE_STORAGE_URL", "http://minio:9000/certificates")

settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
