import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ROOT_PATH = os.getenv("ROOT_PATH", "")
    DAPR_HTTP_PORT = os.getenv("DAPR_HTTP_PORT", "3500")
    PAYMENT_PROCESSING_DAPR_ID = os.getenv(
        "PAYMENT_PROCESSING_DAPR_ID", "payment-processing-service"
    )
    MOJALOOP_CONNECTOR_DAPR_ID = os.getenv(
        "MOJALOOP_CONNECTOR_DAPR_ID", "mojaloop-connector"
    )
    PAYMENT_PROCESSING_BASE_URL = os.getenv("PAYMENT_PROCESSING_BASE_URL", "")
    MOJALOOP_CONNECTOR_BASE_URL = os.getenv("MOJALOOP_CONNECTOR_BASE_URL", "")
    HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "NGN")


def get_config() -> Config:
    return Config()
