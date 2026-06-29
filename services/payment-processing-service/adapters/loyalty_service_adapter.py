from utils import ExternalAPIClient, get_config, create_logger

logger = create_logger(__name__)
config = get_config()


class LoyaltyServiceAdapter(ExternalAPIClient):
    """
    Adapter for loyalty-service.
    Awards loyalty points after successful transactions.
    Failures are swallowed — loyalty processing must never block payments.
    """

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.LOYALTY_SVC_URL,
            headers={"Content-Type": "application/json"},
        )

    def _safe_post(self, endpoint: str, data: dict) -> None:
        try:
            self._post(endpoint=endpoint, data=data, get_response=False)
        except Exception as exc:
            logger.warning("Loyalty ingest call failed endpoint=%s error=%s", endpoint, exc)

    def process_transaction(
        self,
        *,
        user_id: str,
        reference_id: str,
        amount_ngn: float,
        transaction_type: str,
    ) -> None:
        """
        Called after every successful transaction to award loyalty points.
        transaction_type must be one of: cash_in, cash_out, transfer, bill_payment, airtime, data.
        """
        self._safe_post(
            "/loyalty/transactions/process",
            {
                "user_id": user_id,
                "reference_id": reference_id,
                "amount_ngn": amount_ngn,
                "transaction_type": transaction_type,
                "status": "SUCCESS",
            },
        )
