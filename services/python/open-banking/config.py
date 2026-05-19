from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Application Settings
    SERVICE_NAME: str = "OpenBankingAPI"
    VERSION: str = "1.0.0"
    SECRET_KEY: str = Field(..., description="Secret key for security purposes, e.g., token signing.")
    LOG_LEVEL: str = "INFO"

    # Database Settings
    # Use PostgreSQL for a production-ready setup
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "open_banking_db"

    # Construct the database URL
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Load settings
settings = Settings()

# Reconfigure logging with the loaded level
logging.getLogger().setLevel(settings.LOG_LEVEL.upper())
log.info(f"Settings loaded for service: {settings.SERVICE_NAME} (v{settings.VERSION})")
log.debug(f"Database URL: {settings.DATABASE_URL.split('@')[-1]}") # Hide credentials

# Best practice: Create a dummy .env file for local development
# In a real-world scenario, this file would be in .gitignore
# and the SECRET_KEY would be a long, random string.
try:
    with open(".env", "a") as f:
        if "SECRET_KEY" not in open(".env").read():
            f.write("SECRET_KEY=super-secret-key-for-development-only\n")
except FileNotFoundError:
    with open(".env", "w") as f:
        f.write("SECRET_KEY=super-secret-key-for-development-only\n")

# Note: The actual database connection will fail if a PostgreSQL instance is not running.
# This is expected for a production-ready configuration.