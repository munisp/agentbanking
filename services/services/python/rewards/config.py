from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Application Settings
    PROJECT_NAME: str = "Rewards Service API"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, description="Enable debug mode")
    SECRET_KEY: str = Field("super-secret-key", description="Application secret key")

    # Database Settings
    DB_HOST: str = Field("localhost", description="Database host")
    DB_PORT: int = Field(5432, description="Database port")
    DB_USER: str = Field("postgres", description="Database user")
    DB_PASSWORD: str = Field("postgres", description="Database password")
    DB_NAME: str = Field("rewards_db", description="Database name")

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS: list[str] = ["*"]

    @property
    def DATABASE_URL(self) -> str:
        """Constructs the SQLAlchemy database URL."""
        # Using asyncpg for async PostgreSQL driver
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()