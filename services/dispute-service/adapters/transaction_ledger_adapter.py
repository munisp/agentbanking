import os
from utils import ExternalAPIClient
from schemas import Context

class TransactionLedgerAdapter(ExternalAPIClient):
    """Transaction Ledger adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=os.getenv("TRANSACTION_LEDGER_URL", ""),
            headers={
                "Content-Type": "application/json",
            },
        )

    def get_transaction_by_id(self, id: str, context: Context) -> dict:
        """Process a payment through the payment service."""

        try:

            headers = {
                "x-tenant-id": context.tenant_id,
                "x-keycloak-id": context.keycloak_id,
                "x-ledger-id": context.ledger_id
            }

            return self._get(
                endpoint=f"/txn/{id}",
                headers=headers
            )
        except:
            return {
                "message": "Failed",
            }
