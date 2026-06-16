from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Application Settings
    PROJECT_NAME: str = "Infrastructure API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/infrastructure"
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    
    # Security Settings (Placeholder for a real application)
    SECRET_KEY: str = "a_very_secret_key_that_should_be_changed_in_production"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()