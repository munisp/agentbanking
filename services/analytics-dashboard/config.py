
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str = "super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = "postgresql://user:password@postgresserver/db"
    API_KEYS: dict = {"analytics-key": ["read", "write"]}

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

