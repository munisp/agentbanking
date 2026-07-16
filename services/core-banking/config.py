import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Core Banking API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database Settings
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = os.getenv("DB_PORT", 5432)
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_NAME: str = os.getenv("DB_NAME", "core_banking_db")
    
    # Construct the database URL for SQLAlchemy
    # Using asyncpg driver for async operations
    DATABASE_URL: str = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a-very-secret-key-that-should-be-changed-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"] # Allow all for development

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()