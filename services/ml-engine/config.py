from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@db:5432/ml_engine_db"
    api_key: str = "supersecretapikey"
    secret_key: str = "super-secret-key-for-auth"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()

