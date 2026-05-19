from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Application Metadata
    APP_NAME: str = Field("Multi-Currency Accounts API", env="APP_NAME")
    VERSION: str = Field("1.0.0", env="VERSION")
    SECRET_KEY: str = Field("a-very-secret-key-for-jwt-and-stuff", env="SECRET_KEY")
    
    # Database Settings
    DATABASE_URL: str = Field("sqlite:///./multi_currency_accounts.db", env="DATABASE_URL")
    
    # Security Settings (Placeholder for real implementation)
    ALGORITHM: str = Field("HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()