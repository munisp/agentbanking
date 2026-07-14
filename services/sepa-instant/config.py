from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Service Metadata
    SERVICE_NAME: str = "sepa-instant-service"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for managing SEPA Instant Credit Transfers (SCT Inst)."

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./sepa_instant.db"
    # For production, this would be: "postgresql+psycopg2://user:password@host:port/dbname"

    # Security Configuration
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Configuration
    CORS_ORIGINS: List[str] = ["*"] # Allow all for simplicity, restrict in production
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS: List[str] = ["*"]

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()