import logging
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General Settings ---
    PROJECT_NAME: str = "Security Service API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "super-secret-key-for-development-only"  # **MUST** be changed in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Database Settings ---
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "security_db"
    DATABASE_URL: Optional[str] = None

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """
        Constructs the database URL from individual components if DATABASE_URL is not set.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- CORS Settings ---
    BACKEND_CORS_ORIGINS: List[str] = ["*"]  # Allow all for development

    # --- Logging Settings ---
    LOG_LEVEL: str = "INFO"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.setLevel(self.LOG_LEVEL.upper())
        logger.info(f"Configuration loaded for {self.PROJECT_NAME} (v{self.VERSION})")

settings = Settings()
