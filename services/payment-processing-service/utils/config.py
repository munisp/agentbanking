import os

from dotenv import load_dotenv
import utils.bin_list as bin

load_dotenv()


def _parse_bin_env(name: str, default_value) -> list[str]:
    raw_value = os.getenv(name)

    if raw_value is None:
        if isinstance(default_value, list):
            return [str(value).strip() for value in default_value if str(value).strip()]

        raw_value = str(default_value)

    return [value.strip() for value in str(raw_value).split(",") if value.strip()]


class Config:
    """Base config"""

    DATABASE_URI = os.getenv("DATABASE_URI", "")
    ROOT_PATH = os.getenv("ROOT_PATH", "")
    DAPR_PUBSUB_NAME = os.getenv("DAPR_PUBSUB_NAME", "")
    ACCOUNT_SVC_URL = os.getenv("ACCOUNT_SVC_URL", "")
    AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "")
    COMMISSION_SVC_URL = os.getenv(
        "COMMISSION_SVC_URL", "http://commission-settlement:8080"
    )
    LOAN_SVC_URL = os.getenv("LOAN_SVC_URL", "")
    LPO_SVC_URL = os.getenv("LPO_SVC_URL", "")
    INSURANCE_SVC_URL = os.getenv("INSURANCE_SVC_URL", "")
    SUPPLY_CHAIN_SVC_URL = os.getenv("SUPPLY_CHAIN_SVC_URL", "")
    EXCHANGE_RATE_SVC_URL = os.getenv("EXCHANGE_RATE_SVC_URL", "")
    FRAUD_ENGINE_SVC_URL = os.getenv(
        "FRAUD_ENGINE_SVC_URL", "http://fraud-engine.54agent.svc.cluster.local"
    )
    COMPLIANCE_SVC_URL = os.getenv(
        "COMPLIANCE_SVC_URL", "http://cbn-compliance-comprehensive.54agent.svc.cluster.local"
    )
    LOYALTY_SVC_URL = os.getenv(
        "LOYALTY_SVC_URL", "http://loyalty-service.54agent.svc.cluster.local"
    )
    NETWORK_OPS_SVC_URL = os.getenv(
        "NETWORK_OPS_SVC_URL", "http://network-operations.54agent.svc.cluster.local"
    )
    TB_CLUSTER_ID = os.getenv("TB_CLUSTER_ID", "0")
    TB_ADDRESS = os.getenv("TB_ADDRESS", "3000")
    VISA_BINS = _parse_bin_env("VISA_BINS", bin.VISA_BINS)
    MASTERCARD_BINS = _parse_bin_env("MASTERCARD_BINS", bin.MASTERCARD_BINS)
    VERVE_BINS = _parse_bin_env("VERVE_BINS", bin.VERVE_BINS)
    AMEX_BINS = _parse_bin_env("AMEX_BINS", bin.AMEX_BINS)
    DISCOVER_BINS = _parse_bin_env("DISCOVER_BINS", bin.DISCOVER_BINS)
    CARD_SVC_URL = os.getenv("CARD_SVC_URL", "")
    CORE_BANKING_CONNECT_DAPR_ID = os.getenv(
        "CORE_BANKING_CONNECT_DAPR_ID", "payment-processing-service"
    )
    PAYMENT_RAILS_CONNECTORS_DAPR_ID = os.getenv(
        "PAYMENT_RAILS_CONNECTORS_DAPR_ID", "payment-rails-connectors"
    )
    STATE_STORE_NAME = os.getenv("STATE_STORE_NAME", "statestore")
    SYSTEM_AGENT_ID = os.getenv("SYSTEM_AGENT_ID", "00000000-0000-0000-0000-000000000000")


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
