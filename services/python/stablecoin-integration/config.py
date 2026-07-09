from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/stablecoin_integration"
    ASYNC_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stablecoin_integration"

    # Application Settings
    PROJECT_NAME: str = "Stablecoin Integration Service"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"] # Allow all for development

    # Security Settings (Placeholder for real-world implementation)
    SECRET_KEY: str = "super-secret-key-for-testing"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()