from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from schemas import Context
from utils import ExternalAPIClient, get_config, create_logger

logger = create_logger(__name__)
config = get_config()


class CommissionServiceAdapter:
    def __init__(self):
        self._client = ExternalAPIClient(
            base_url=config.COMMISSION_SVC_URL,
            headers={"Content-Type": "application/json"},
        )

    @staticmethod
    def _stable_uuid(value: str) -> uuid.UUID:
        normalized_value = str(value or "").strip()
        if not normalized_value:
            return uuid.uuid4()

        try:
            return uuid.UUID(normalized_value)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_URL, normalized_value)

    def create_commission(
        self,
        *,
        agent_id: str,
        transaction_type: str,
        transaction_ref: str,
        amount: float,
        currency: str,
        context: Context,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload = {
            "agent_id": str(self._stable_uuid(agent_id)),
            "transaction_id": str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{context.tenant_id}:{transaction_type}:{transaction_ref}",
                )
            ),
            "transaction_ref": transaction_ref,
            "transaction_type": transaction_type,
            "amount": float(amount),
            "currency": str(currency).upper() or "NGN",
            "earned_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metadata": metadata or {},
        }

        logger.info(
            "Creating commission transaction_type=%s ref=%s amount=%s currency=%s",
            transaction_type,
            transaction_ref,
            amount,
            currency,
        )

        return self._client._post("/api/v1/commissions", data=payload)

    @staticmethod
    def _to_minor_units(amount: float) -> int:
        return int(round(float(amount)))

    def calculate_commission(
        self,
        *,
        agent_id: str,
        transaction_type: str,
        transaction_ref: str,
        amount: float,
        currency: str,
        context: Context,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        commission = self.create_commission(
            agent_id=agent_id,
            transaction_type=transaction_type,
            transaction_ref=transaction_ref,
            amount=amount,
            currency=currency,
            context=context,
            metadata=metadata,
        )

        commission_amount = float(commission.get("commission_amount") or 0)
        gross_minor = self._to_minor_units(amount)
        commission_minor = self._to_minor_units(commission_amount)
        net_minor = gross_minor - commission_minor

        if net_minor <= 0:
            raise Exception(
                f"Commission exceeds or equals the transaction amount for {transaction_type}"
            )
        logger.info(
            "Calculated commission for transaction_type=%s ref=%s: gross=%.2f %s, commission=%.2f %s, net=%.2f %s",
            transaction_type,
            transaction_ref,
            amount, currency,
            commission_amount, currency,
            amount - commission_amount, currency,
        )

        commission["gross_amount"] = float(amount)
        commission["gross_amount_minor"] = gross_minor
        commission["net_amount_minor"] = net_minor
        return commission
