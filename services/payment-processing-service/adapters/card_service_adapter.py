from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context
from bins import VISA_BINS, MASTERCARD_BINS, VERVE_BINS, AMEX_BINS, DISCOVER_BINS

logger = create_logger(__name__)
config = get_config()

# BIN lookup map — order matters, more specific schemes first
BIN_SCHEME_MAP = [
    ("VERVE",      VERVE_BINS),       # Check Verve first — some overlap with Visa/Discover
    ("AMEX",       AMEX_BINS),        # 34, 37 — before Mastercard
    ("MASTERCARD", MASTERCARD_BINS),
    ("VISA",       VISA_BINS),        # 4 is broad — check last among credit schemes
    ("DISCOVER",   DISCOVER_BINS),
]

# Route each scheme to its endpoint
SCHEME_ENDPOINTS = {
    "VISA":       "/card/visa/transaction",
    "MASTERCARD": "/card/mastercard/transaction",
    "VERVE":      "/card/verve/transaction",
    "AMEX":       "/card/amex/transaction",
    "DISCOVER":   "/card/discover/transaction",
}


class CardServiceAdapter(ExternalAPIClient):
    """Card service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.CARD_SVC_URL,
            headers={"Content-Type": "application/json"},
        )

    def get_card_by_account_id(self, account_id: str, context: Context):
        """Retrieve card by account ID."""
        return self._get(
            endpoint=f"/card/account/{account_id}",
            headers=self._build_headers(context)
        )

    def debit_card(
        self,
        card_number: str,
        card_cvv: str,
        card_expiry: str,
        card_pin: str,
        amount: float,
        context: Context
    ):
        """Identify card scheme and perform debit transaction."""

        scheme = self.identify_card(card_number)
        logger.info(f"Card identified as {scheme} | tenant={context.tenant_id}")

        payload = {
            "card_number": card_number,
            "card_cvv": card_cvv,
            "card_expiry": card_expiry,
            "card_pin": card_pin,
            "amount": amount,
            "type": scheme
        }

        return self.perform_transaction(payload, context)

    def identify_card(self, card_number: str) -> str:
        """Identify card scheme from BIN (first 6-8 digits).
        
        Context not needed here — pure logic, no I/O.
        """
        bin6 = card_number[:6]
        bin8 = card_number[:8]

        for scheme, bins in BIN_SCHEME_MAP:
            for prefix in bins:
                if bin6.startswith(prefix) or bin8.startswith(prefix):
                    return scheme

        raise ValueError(f"Unsupported card type for BIN: {bin6}")

    def perform_transaction(self, payload: dict, context: Context):
        """Route transaction to the correct card scheme endpoint."""

        scheme = payload.get("type")
        endpoint = SCHEME_ENDPOINTS.get(scheme)

        if not endpoint:
            raise ValueError(f"Unsupported card type: {scheme}")

        logger.info(f"Routing {scheme} transaction to {endpoint} | tenant={context.tenant_id}")

        return self._post(       
            endpoint=endpoint,
            json=payload,
            headers=self._build_headers(context)
        )

    def _build_headers(self, context: Context) -> dict:
        """Build common context headers — avoids repeating in every method."""
        return {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id,
            "x-ledger-id": context.ledger_id
        }