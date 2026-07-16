import logging
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "sqlite:///./fraud_detection.db"
    ASYNC_DATABASE_URL: str = "sqlite+aiosqlite:///./fraud_detection.db"

    # Application Settings
    PROJECT_NAME: str = "Fraud Detection API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Security Settings
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"] # Allow all for development

    # ML Model Settings
    ML_MODEL_VERSION: str = "v1.0.0_hybrid"
    ML_MODEL_ENDPOINT: Optional[str] = None # Production implementation for external ML service

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

if settings.DEBUG:
    log.setLevel(logging.DEBUG)
    log.debug("Settings loaded in DEBUG mode.")
else:
    log.setLevel(logging.INFO)
    log.info("Settings loaded in PRODUCTION mode.")