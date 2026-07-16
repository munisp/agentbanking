from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context

logger = create_logger(__name__)
config = get_config()

class SupplyChainServiceAdapter(ExternalAPIClient):
    """Supply chain service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.SUPPLY_CHAIN_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def get_financing_details(self, financing_id: str, context: Context):
        """Get financing details."""

        return self._get(
            endpoint=f"/api/v1/supply-chain/financing/{financing_id}",
            headers={
                "x-tenant-id": context.tenant_id,
                "x-keycloak-id": context.keycloak_id,
                "x-mint-account-id": context.mint_account_id,
                "x-ledger-id": context.ledger_id
            }
        )

    def record_payment(self, transaction_id: str, financing_id: str, amount: int, payment_date: str, payment_method: str, context: Context):
        """Record financing payment."""

        payload = {
            "transaction_id": transaction_id,
            "amount": amount,
            "payment_date": payment_date,
            "payment_method": payment_method
        } 

        return self._post(
            endpoint=f"/api/v1/system/supply-chain/financing/record-payment/{financing_id}",
            data=payload,
            headers={
                "x-tenant-id": context.tenant_id,
                "x-keycloak-id": context.keycloak_id,
                "x-mint-account-id": context.mint_account_id,
                "x-ledger-id": context.ledger_id
            }
        )
