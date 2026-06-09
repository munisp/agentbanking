from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List

class Settings(BaseSettings):
    # Application Settings
    PROJECT_NAME: str = "AI/ML Model Serving API"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, description="Enable debug mode")
    SECRET_KEY: str = Field("a-very-secret-key-for-development", description="Secret key for security")
    
    # Database Settings
    DATABASE_URL: str = Field("postgresql://postgres:postgres@localhost:5432/ai_ml_services", description="Database connection URL")
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"] # Allow all for development, should be restricted in production
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
