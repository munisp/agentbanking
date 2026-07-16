from utils import ExternalAPIClient, get_config, create_logger

logger = create_logger(__name__)
config = get_config()

class LpoServiceAdapter(ExternalAPIClient):
    """Lpo service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.LPO_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def get_lpo_details(self, lpo_id: str, tenant_id: str):
        """Get loan details."""

        return self._get(
            endpoint=f"/api/v1/lpo/{lpo_id}",
            headers={
                "x-tenant-id": tenant_id,
            }
        )

    def record_payment(self, transaction_id: str, lpo_id: str, amount: int, payment_date: str, payment_method: str, tenant_id: str):
        """Record loan payment."""

        payload = {
            "transaction_id": transaction_id,
            "amount": amount,
            "payment_date": payment_date,
            "payment_method": payment_method
        }

        return self._post(
            endpoint=f"/api/v1/lpo/{lpo_id}/record-payment",
            data=payload,
            headers={
                "x-tenant-id": tenant_id,
            }
        )
