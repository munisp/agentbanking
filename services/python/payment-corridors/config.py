from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database settings
    # Default to a local SQLite file for development/testing
    DATABASE_URL: str = "sqlite:///./payment_corridors.db"
    
    # Application settings
    PROJECT_NAME: str = "Payment Corridors API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Security settings (placeholder for production)
    SECRET_KEY: str = "a-very-secret-key-for-development-change-this-in-prod"
    ALGORITHM: str = "HS256"
    
    # CORS settings
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost", "http://localhost:8080"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
