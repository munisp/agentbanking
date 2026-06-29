import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base config"""

    DATABASE_URI: str = os.getenv("DATABASE_URI", "")
    ROOT_PATH: str = os.getenv("ROOT_PATH", "")
    DAPR_PUBSUB_NAME: str = os.getenv("DAPR_PUBSUB_NAME", "")
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    KAFKA_SECURITY_PROTOCOL: str = os.getenv("KAFKA_SECURITY_PROTOCOL", "")
    KAFKA_SASL_MECHANISM: str = os.getenv("KAFKA_SASL_MECHANISM", "")
    KAFKA_SASL_USERNAME: str = os.getenv("KAFKA_SASL_USERNAME", "")
    KAFKA_SASL_PASSWORD: str = os.getenv("KAFKA_SASL_PASSWORD", "")
    AUDIT_SVC_URL: str = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")
    COMPLIANCE_SVC_URL: str = os.getenv("COMPLIANCE_SVC_URL", "https://54agent.upi.dev/compliance")


class DevelopmentConfig(Config):
    DEBUG: bool = True


class ProductionConfig(Config):
    DEBUG: bool = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

config_name = os.getenv("FLASK_ENV", "development")


def get_config() -> Config:
    config_class = config_map.get(config_name)
    if config_class is None:
        raise Exception(f"Config {config_name} not found")
    return config_class()
