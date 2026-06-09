from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://user:password@localhost:5432/edgedb"
    secret_key: str = "super-secret-key" # Change this in production
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    log_level: str = "INFO"

settings = Settings()

