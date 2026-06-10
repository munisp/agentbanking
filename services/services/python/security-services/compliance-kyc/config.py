from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import logging

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = Field(..., description="The database connection URL.")
    
    # Application Settings
    PROJECT_NAME: str = "Compliance-KYC Service"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "super-secret-key-for-testing-only" # Should be loaded from environment in production
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    
    # Security Settings
    # A simple mock for demonstration. In a real app, this would involve proper JWT/OAuth2 settings.
    MOCK_AUTH_ENABLED: bool = True 

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Configure basic logging
logging.basicConfig(level=settings.LOG_LEVEL,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.PROJECT_NAME)

# Set the logger level based on settings
logger.setLevel(settings.LOG_LEVEL)