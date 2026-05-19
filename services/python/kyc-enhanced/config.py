from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Core application settings
    PROJECT_NAME: str = "KYC Enhanced Due Diligence API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./kyc_enhanced.db"
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    
    # Security settings (Placeholder for real-world implementation)
    SECRET_KEY: str = "SUPER_SECRET_KEY_FOR_DEV"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()