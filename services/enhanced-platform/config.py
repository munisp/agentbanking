from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Enhanced Platform API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, description="Enable debug mode")

    # Database Settings
    DATABASE_URL: str = Field(
        "postgresql+asyncpg://user:password@localhost/enhanced_platform_db",
        description="Asynchronous database connection URL"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def ensure_asyncpg_driver(cls, v: str) -> str:
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            return v.replace("://", "+asyncpg://", 1)
        return v
    
    # Security Settings
    SECRET_KEY: str = Field(
        "a-very-secret-key-that-should-be-changed-in-production",
        description="JWT secret key"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"] # Should be restricted in production

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
