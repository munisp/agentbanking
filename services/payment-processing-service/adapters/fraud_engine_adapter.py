from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context

logger = create_logger(__name__)
config = get_config()


class FraudEngineAdapter(ExternalAPIClient):
    """Fraud engine service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.FRAUD_ENGINE_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def score_transaction(self, payload: dict, context: Context):
        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id,
        }
        return self._post(endpoint="/api/v1/fraud/score", data=payload, headers=headers)
