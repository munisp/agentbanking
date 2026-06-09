from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "FPS Integration Service"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    
    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/fps_integration",
        description="Database connection URL (e.g., postgresql://user:pass@host:port/db or postgresql://user:pass@host:port/db)"
    )
    
    # Security Settings
    SECRET_KEY: str = Field(
        default="super-secret-key-for-testing-only",
        description="Secret key for token encoding/decoding. CHANGE THIS IN PRODUCTION!"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
