from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Core settings
    PROJECT_NAME: str = "User Onboarding Enhanced API"
    VERSION: str = "1.0.0"
    
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/user_onboarding_enhanced"
    
    # Security settings
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production" # Production implementation, should be loaded from env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS settings
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()