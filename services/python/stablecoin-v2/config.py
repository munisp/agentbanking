from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Core settings
    APP_NAME: str = "Stablecoin V2 API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/stablecoin_v2"

    # Security settings
    SECRET_KEY: str = "super-secret-key-for-development-do-not-use-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS settings
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()