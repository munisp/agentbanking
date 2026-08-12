from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Database Settings
    DATABASE_URL: str = "sqlite:///./upi_integration.db"

    # Security Settings
    SECRET_KEY: str = "a-very-secret-key-that-should-be-changed-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Application Settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SERVICE_NAME: str = "upi-integration"

    # Payment Gateway (PSP) Settings — real provider, configured via env
    PG_BASE_URL: Optional[str] = None
    PG_API_KEY: Optional[str] = None
    PG_TIMEOUT_SECONDS: float = 15.0

    # Payment Gateway Simulation (explicitly gated; forbidden in production)
    PG_SIMULATION_MODE: bool = False
    PG_MOCK_SUCCESS_RATE: float = 0.0
    PG_MOCK_REFUND_SUCCESS_RATE: float = 0.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

# Hard-fail at startup if the simulator is enabled in production.
if settings.PG_SIMULATION_MODE and settings.ENVIRONMENT.lower() == "production":
    raise RuntimeError(
        "PG_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production. "
        "Refusing to start with a simulated payment gateway."
    )
