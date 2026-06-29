from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context

logger = create_logger(__name__)
config = get_config()

class InsuranceServiceAdapter(ExternalAPIClient):
    """Insurance service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.INSURANCE_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def get_insurance_policy_details(self, policy_id: str, context: Context):
        """Get insurance policy details."""

        return self._get(
            endpoint=f"/api/v1/insurance/policies/{policy_id}",
            headers={
                "x-tenant-id": context.tenant_id,
                "x-keycloak-id": context.keycloak_id
            }
        )

    def record_payment(self, transaction_id: str, policy_id: str, amount: int, payment_date: str, payment_method: str, context: Context):
        """Record insurance premium payment."""

        payload = {
            "transaction_id": transaction_id,
            "amount": amount,
            "payment_date": payment_date,
            "payment_method": payment_method
        } 

        return self._post(
            endpoint=f"/api/v1/system/insurance/premiums/record-payment/{policy_id}",
            data=payload,
            headers={
                "x-tenant-id": context.tenant_id,
                "x-keycloak-id": context.keycloak_id
            }
        )
