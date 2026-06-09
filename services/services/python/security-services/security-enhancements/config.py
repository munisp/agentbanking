from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database Settings
    DATABASE_URL: str = Field(
        ...,
        description="The connection URL for the PostgreSQL database.",
        env="DATABASE_URL"
    )

    # Application Settings
    PROJECT_NAME: str = "Security Enhancements API"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, description="Enable debug mode.")

    # Security Settings
    SECRET_KEY: str = Field(
        ...,
        description="The secret key used for cryptographic operations (e.g., API key hashing).",
        env="SECRET_KEY"
    )
    
    # CORS Settings
    CORS_ORIGINS: list[str] = Field(
        ["*"],
        description="A list of origins that should be permitted to make cross-origin requests.",
        env="CORS_ORIGINS"
    )

settings = Settings()