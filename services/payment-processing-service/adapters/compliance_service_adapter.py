from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context

logger = create_logger(__name__)
config = get_config()

CTR_THRESHOLD_NGN = 5_000_000.0


class ComplianceServiceAdapter(ExternalAPIClient):
    """
    Adapter for cbn-compliance-comprehensive service.
    Used to report large transactions (CTR) and per-transaction stats
    so Monthly Activity Reports and CTR reports reflect live data.
    Failures are swallowed — compliance reporting must never block payments.
    """

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.COMPLIANCE_SVC_URL,
            headers={"Content-Type": "application/json"},
        )

    def _safe_post(self, endpoint: str, data: dict) -> None:
        try:
            self._post(endpoint=endpoint, data=data, get_response=False)
        except Exception as exc:
            logger.warning("Compliance ingest call failed endpoint=%s error=%s", endpoint, exc)

    def notify_transaction(
        self,
        *,
        transaction_id: str,
        transaction_type: str,
        amount_ngn: float,
        currency: str = "NGN",
        agent_id: str,
        customer_name: str = "",
        customer_bvn: str | None = None,
        customer_account: str = "",
        transaction_date: str,
    ) -> None:
        """
        Called after every successful transaction.
        Always records stats for Monthly Activity Reports.
        Also files a CTR record if amount >= NGN 5M.
        """
        self._safe_post(
            "/api/v1/agent-stats/record",
            {
                "transaction_type": transaction_type,
                "amount_ngn": amount_ngn,
                "period": transaction_date[:7],  # YYYY-MM
            },
        )

        if amount_ngn >= CTR_THRESHOLD_NGN and currency.upper() == "NGN":
            self._safe_post(
                "/api/v1/ctr-ingest",
                {
                    "transaction_id": transaction_id,
                    "transaction_type": transaction_type,
                    "amount": amount_ngn,
                    "currency": currency,
                    "agent_id": agent_id,
                    "customer_name": customer_name,
                    "customer_bvn": customer_bvn,
                    "customer_account": customer_account,
                    "transaction_date": transaction_date,
                },
            )
            logger.info(
                "CTR ingest triggered transaction_id=%s amount=%.2f",
                transaction_id, amount_ngn,
            )

    def notify_fraud(
        self,
        *,
        fraud_type: str,
        amount_attempted: float,
        channel: str,
        incident_date: str,
        victim_account: str = "",
        perpetrator_info: str = "",
    ) -> None:
        """Called by fraud pre-check when a transaction is blocked."""
        self._safe_post(
            "/api/v1/fraud-ingest",
            {
                "fraud_type": fraud_type,
                "amount_attempted": amount_attempted,
                "amount_lost": 0,
                "channel": channel,
                "incident_date": incident_date,
                "victim_account": victim_account,
                "perpetrator_info": perpetrator_info,
            },
        )
