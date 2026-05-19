from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = Field(..., description="The SQLAlchemy database connection URL.")
    
    # Security Settings
    API_KEY_SECRET: str = Field("super-secret-key", description="Secret key used for hashing and validating API keys.")
    API_KEY_ALGORITHM: str = Field("HS256", description="Algorithm used for API key hashing.")
    
    # Logging Settings
    LOG_LEVEL: str = Field("INFO", description="The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).")
    
    # API Metadata
    PROJECT_NAME: str = Field("White-Label Identity Verification API", description="The name of the project.")
    PROJECT_VERSION: str = Field("1.0.0", description="The version of the project.")
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()