"""Configuration for Multi-SIM Failover Service."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("MULTI_SIM_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/platform")
    SERVICE_PORT: int = int(os.getenv("MULTI_SIM_PORT", "8030"))

    class Config:
        env_prefix = "MULTI_SIM_"


settings = Settings()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
