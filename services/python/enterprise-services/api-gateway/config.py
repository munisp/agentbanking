from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = Field(..., description="The SQLAlchemy database connection URL.")
    
    # Application Settings
    PROJECT_NAME: str = "API Gateway Configuration Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Security Settings
    SECRET_KEY: str = Field(..., description="Secret key for application security.")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings(
    # Provide a default for local development if .env is missing
    DATABASE_URL="postgresql://postgres:postgres@localhost:5432/enterprise_services",
    SECRET_KEY="super-secret-key"
)