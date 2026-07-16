
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Email Service"
    database_url: str = "postgresql://user:password@postgresserver/db"
    secret_key: str = "super-secret-key-replace-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env")

@lru_cache()
def get_settings():
    return Settings()


