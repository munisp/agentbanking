from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/payment"
    ECHO_SQL: bool = False

    # Application Settings
    SERVICE_NAME: str = "PaymentService"
    DEBUG: bool = True
    VERSION: str = "1.0.0"
    SECRET_KEY: str = "YOUR_SECRET_KEY_FOR_JWT_OR_OTHER_SECURITY" # Production implementation, should be loaded from env

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    # Security Settings (Basic for demonstration, full auth/auth is complex)
    # In a real-world scenario, this would involve OAuth2/JWT configuration
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY_VALUE: str = "super-secret-api-key"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()