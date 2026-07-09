from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/cross_border"
    
    # Application Settings
    PROJECT_NAME: str = "Cross-Border Payments API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS: list[str] = ["*"]
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    
    # Security Settings (Placeholder for real-world implementation)
    SECRET_KEY: str = "super-secret-key-for-development"
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()