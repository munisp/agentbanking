import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base config"""

    DATABASE_URL = os.getenv("DATABASE_URL", "")
    PORT = int(os.getenv("PORT", "8011"))
    SERVICE_NAME = os.getenv("SERVICE_NAME", "support-comms-service")


class DevelopmentConfig(Config):
    """Development specific config"""

    DEBUG = True


class ProductionConfig(Config):
    """Production specific config"""

    DEBUG = False


config = {"development": DevelopmentConfig, "production": ProductionConfig}

config_name = os.getenv("APP_ENV", "development")


def get_config() -> Config:
    config_data = config.get(config_name)

    if config_data is None:
        raise Exception("Config {} not found".format(config_name))

    return config_data
