from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database settings
        DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/payment_corridors"
    
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
