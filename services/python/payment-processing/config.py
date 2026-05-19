from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Model configuration
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core Service Settings
    SERVICE_NAME: str = "payment-processing"
    SECRET_KEY: str = "super-secret-key-for-production-change-me"
    LOG_LEVEL: str = "INFO"
    
    # Database Settings
    # Using asyncpg for PostgreSQL in a production environment, but defaulting to aiosqlite for sandbox/testing
    # Production URL example: postgresql+asyncpg://user:password@host:port/dbname
    DATABASE_URL: str = "sqlite+aiosqlite:///./payment_processing.db"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"] # Be more restrictive in production
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS: List[str] = ["*"]

    # External Service Settings (Simulated PSP)
    PSP_API_KEY: str = "simulated-psp-api-key"
    PSP_BASE_URL: str = "https://api.simulated-psp.com"

settings = Settings()
