import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base config"""

    AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "")
    DATABASE_URI = os.getenv("DATABASE_URI", "")
    KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "")
    KEYCLOAK_ADMIN_USERNAME = os.getenv("KEYCLOAK_ADMIN_USERNAME", "")
    KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "")
    ROOT_PATH = os.getenv("ROOT_PATH", "/")
    DAPR_PUBSUB_NAME = os.getenv("DAPR_PUBSUB_NAME", "")
    DEFAULT_KEYCLOAK_REALM = os.getenv("DEFAULT_KEYCLOAK_REALM", "")
    DEFAULT_KEYCLOAK_PUBLIC_KEY = os.getenv("DEFAULT_KEYCLOAK_PUBLIC_KEY", "")
    DEFAULT_SUPER_ADMIN_NAME = os.getenv("DEFAULT_SUPER_ADMIN_NAME", "")
    DEFAULT_SUPER_ADMIN_EMAIL = os.getenv("DEFAULT_SUPER_ADMIN_EMAIL", "")
    DEFAULT_SUPER_ADMIN_PASSWORD = os.getenv("DEFAULT_SUPER_ADMIN_PASSWORD", "")
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "")
    KAFKA_SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME", "")
    KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "")

    # VPN Detection Settings
    BLOCK_VPN = os.getenv("BLOCK_VPN", "true").lower() == "true"
    BLOCK_TOR = os.getenv("BLOCK_TOR", "true").lower() == "true"
    BLOCK_DATACENTER = os.getenv("BLOCK_DATACENTER", "false").lower() == "true"


class DevelopmentConfig(Config):
    """Development specific config"""

    DEBUG = True


class ProductionConfig(Config):
    """Production specific config"""

    DEBUG = False


config = {"development": DevelopmentConfig, "production": ProductionConfig}

config_name = os.getenv("FLASK_ENV", "development")


def get_config() -> Config:
    config_data = config.get(config_name)

    if config_data is None:
        raise Exception("Config {} not found".format(config_name))

    return config_data
