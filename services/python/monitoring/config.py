from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./monitoring.db"
    
    # Application Configuration
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Security Configuration
    # In a real application, you would have more complex security settings
    # such as JWT algorithm, token expiration, etc.
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()