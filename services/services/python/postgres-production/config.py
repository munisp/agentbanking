import logging
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application Settings ---
    PROJECT_NAME: str = "Postgres Production Service"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "A production-ready FastAPI service for managing application configurations in a PostgreSQL database."
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    API_PREFIX: str = "/api/v1"
    
    # --- Database Settings ---
    POSTGRES_USER: str = Field(..., description="PostgreSQL database user")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL database password")
    POSTGRES_SERVER: str = Field(..., description="PostgreSQL database server host or IP")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL database port")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    
    @property
    def DATABASE_URL(self) -> str:
        """
        Constructs the SQLAlchemy database URL.
        """
        # Using 'psycopg2' driver for production-readiness (async drivers like 'asyncpg' are also common)
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- CORS Settings ---
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="List of origins allowed to make cross-origin requests. Use ['*'] for all."
    )

    # --- Security Settings (Placeholder for a real implementation) ---
    SECRET_KEY: str = Field(
        default="super-secret-key-for-development-only",
        description="Secret key for security purposes (e.g., JWT signing). MUST be changed in production."
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days

# Instantiate settings
settings = Settings()

# Log a confirmation message
logger.info(f"Settings loaded for project: {settings.PROJECT_NAME} (Debug: {settings.DEBUG})")

# Example usage of a required environment variable check
if settings.POSTGRES_USER == "postgres_user":
    logger.warning("Using default placeholder for POSTGRES_USER. Please set environment variables.")