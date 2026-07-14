from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context

logger = create_logger(__name__)
config = get_config()


class AccountServiceAdapter(ExternalAPIClient):
    """Account service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.ACCOUNT_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def get_account_by_account_id(self, account_id: str, context: Context):
        """Retrieve account by account ID. Handles 'MINT_ACCOUNT' as a special case."""

        if account_id == "MINT_ACCOUNT":
            # Return a default/fake account object for mint/system account
            return {
                "id": 0,
                "name": "Mint Account",
                "type": "system",
                "status": "active",
            }

        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": "system",
            "x-ledger-id": "1",  # TODO: Default ledger ID.
        }

        try:
            return self._get(endpoint=f"/account/{account_id}", headers=headers)
        except Exception as e:
            logger.error(f"Account lookup failed for account_id={account_id}: {e}")
            return (
                {}
            )  # Fallback to empty dict on error - Ensure transaction processing continues.
