"""
Recurring Payments Configuration
Service configuration and settings
"""

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Service settings"""
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/recurring_payments"
    
    # Service
    SERVICE_NAME: str = "recurring-payments"
    SERVICE_VERSION: str = "1.0.0"
    
    # API
    API_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings"""
    return Settings()
