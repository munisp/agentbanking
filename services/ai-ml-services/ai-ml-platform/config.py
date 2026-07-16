from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application Settings ---
    PROJECT_NAME: str = "AI/ML Platform API"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, description="Enable debug mode")

    # --- Database Settings ---
    POSTGRES_USER: str = Field(..., description="PostgreSQL database user")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL database password")
    POSTGRES_SERVER: str = Field("localhost", description="PostgreSQL database server host")
    POSTGRES_PORT: int = Field(5432, description="PostgreSQL database server port")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")

    @property
    def DATABASE_URL(self) -> str:
        """Constructs the database URL for SQLAlchemy."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Security Settings ---
    SECRET_KEY: str = Field(..., description="Secret key for JWT encoding")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days

settings = Settings()