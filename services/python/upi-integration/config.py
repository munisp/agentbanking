from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/upi_integration"

    # Security Settings
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Application Settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "upi-integration"

    # Payment Gateway Mock Settings (for demonstration)
    PG_MOCK_SUCCESS_RATE: float = 0.9
    PG_MOCK_REFUND_SUCCESS_RATE: float = 0.8

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()