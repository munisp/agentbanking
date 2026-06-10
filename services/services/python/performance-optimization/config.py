from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("performance_optimization_service")

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Performance Optimization Service"
    DEBUG: bool = Field(False, description="Enable debug mode")
    VERSION: str = "1.0.0"
    
    # Database Settings
    DATABASE_URL: str = Field(
        "postgresql://postgres:postgres@localhost:5432/performance_optimization", 
        description="Database connection URL. Use postgresql://user:pass@host:port/db for production."
    )
    
    # Security Settings (Placeholder for production readiness)
    SECRET_KEY: str = Field("a-very-secret-key-that-should-be-changed-in-prod", description="Secret key for JWT/session management")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
