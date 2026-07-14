from typing import Optional

from utils import ExternalAPIClient, get_config, create_logger

logger = create_logger(__name__)
config = get_config()


class NetworkOpsAdapter:
    def __init__(self):
        self._client = ExternalAPIClient(
            base_url=config.NETWORK_OPS_SVC_URL,
            headers={"Content-Type": "application/json"},
        )

    def register_transaction(
        self,
        *,
        tx_type: str,
        channel: str,
        medium: str,
        status: str,
        amount: Optional[float] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        payload: dict = {
            "type": tx_type,
            "channel": channel,
            "medium": medium,
            "status": status,
        }
        if amount is not None:
            payload["amount"] = amount
        if agent_id:
            payload["agent_id"] = agent_id

        self._client._post("/api/v1/transactions", data=payload)
