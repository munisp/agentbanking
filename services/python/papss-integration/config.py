from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    
    # Core Application Settings
    PROJECT_NAME: str = "PAPSS Integration Service"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(..., description="Secret key for security purposes.")
    
    # Database Settings
        # e.g., "postgresql://user:password@host:port/dbname"
    DATABASE_URL: str = Field(..., description="The database connection URL.")
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    
    # Security Settings
    # In a real application, you would add more security-related settings here
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Initialize settings instance
settings = Settings(_env_file=".env")

# Example .env content for local development (not written to file, just for context)
# DATABASE_URL="postgresql://postgres:postgres@localhost:5432/papss_integration"
# SECRET_KEY="a_very_secret_key_that_should_be_changed_in_production"
