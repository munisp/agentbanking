from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Application Settings
    PROJECT_NAME: str = "AI Platform Service"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "a_very_secret_key_for_testing" # In a real app, this should be a complex, randomly generated string
    
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_ml_services"
    
    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
