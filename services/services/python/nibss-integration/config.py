from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = Field("postgresql://postgres:postgres@localhost:5432/nibss_integration", env="DATABASE_URL", description="Database connection URL")
    
    # Application Settings
    PROJECT_NAME: str = "NIBSS Integration Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, env="DEBUG")
    
    # NIBSS API Credentials (Placeholder for security)
    NIBSS_API_KEY: str = Field("your_nibss_api_key", env="NIBSS_API_KEY")
    NIBSS_SECRET: str = Field("your_nibss_secret", env="NIBSS_SECRET")
    NIBSS_BASE_URL: str = Field("https://nibss-api.example.com/v1", env="NIBSS_BASE_URL")
    
    # Logging Settings
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
