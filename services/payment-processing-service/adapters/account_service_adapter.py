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

    def check_account(self, account_id: str, pin: str, context: Context):
        """Validate account pin."""

        payload = {"account_id": account_id, "pin": pin}

        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id,
        }

        self._post(endpoint="/account/check-account", data=payload, headers=headers)

    def get_account_by_keycloak_id(self, keycloak_id: str, context: Context):
        """Retrieve account by keycloak ID."""

        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id,
        }

        return self._get(endpoint=f"/account/keycloak/{keycloak_id}", headers=headers)

    def get_account_by_account_number(self, account_number: str, context: Context):
        """Retrieve account by account ID."""

        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id,
        }

        return self._get(
            endpoint=f"/account/account-number/{account_number}", headers=headers
        )

    def get_account_by_id(self, account_id: str, context: Context):
        """Retrieve account by account ID."""

        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id,
        }

        return self._get(endpoint=f"/account/{account_id}", headers=headers)

    def get_mint_account_by_ledger(self, context: Context):
        """Retrieve mint account for the specified ledger."""

        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id,
        }

        return self._get(endpoint="/system", headers=headers)
