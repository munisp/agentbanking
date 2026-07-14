from typing import Dict

import httpx

from .config import get_config
from .helpers import create_logger

logger = create_logger(__name__)
config = get_config()


def _build_service_base_url(explicit_url: str, dapr_app_id: str) -> str:
    if explicit_url:
        return explicit_url.rstrip("/")

    return f"http://localhost:{config.DAPR_HTTP_PORT}/v1.0/invoke/{dapr_app_id}/method"


class PaymentProcessingClient:
    def __init__(self):
        self.base_url = _build_service_base_url(
            config.PAYMENT_PROCESSING_BASE_URL,
            config.PAYMENT_PROCESSING_DAPR_ID,
        )
        self.client = httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS)

    async def external_debit(self, payload: Dict, headers: Dict[str, str]) -> Dict:
        logger.info("Invoking payment-processing external debit")

        response = await self.client.post(
            f"{self.base_url}/payment/transfer/debit",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


class MojaloopConnectorClient:
    def __init__(self):
        self.base_url = _build_service_base_url(
            config.MOJALOOP_CONNECTOR_BASE_URL,
            config.MOJALOOP_CONNECTOR_DAPR_ID,
        )
        self.client = httpx.AsyncClient(timeout=config.HTTP_TIMEOUT_SECONDS)

    async def initiate_transfer(self, payload: Dict, headers: Dict[str, str]) -> Dict:
        logger.info("Invoking mojaloop transfer initiation")

        response = await self.client.post(
            f"{self.base_url}/transfers/initiate",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
