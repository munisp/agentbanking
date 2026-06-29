from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import logging

class Settings(BaseSettings):
    # Model configuration
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application Settings
    APP_NAME: str = Field("Integrations Service", description="Name of the application.")
    DEBUG: bool = Field(False, description="Enable debug mode.")
    SECRET_KEY: str = Field("super-secret-key", description="Secret key for security.")
    
    # Database Settings
    DB_USER: str = Field("postgres", description="Database username.")
    DB_PASSWORD: str = Field("postgres", description="Database password.")
    DB_HOST: str = Field("localhost", description="Database host.")
    DB_PORT: int = Field(5432, description="Database port.")
    DB_NAME: str = Field("integrations_db", description="Database name.")
    
    @property
    def DATABASE_URL(self) -> str:
        # Using psycopg2 driver for synchronous SQLAlchemy
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Logging Settings
    LOG_LEVEL: str = Field("INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).")

# Initialize settings
settings = Settings()

# Configure basic logging
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.APP_NAME)
