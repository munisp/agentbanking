import json

from dapr.clients import DaprClient

from utils import get_config, create_logger

# Setup config
config = get_config()

logger = create_logger(__name__)


class CoreBankingAdapter:
    def __init__(self):
        self._dapr_client = None

    @property
    def dapr_client(self):
        if self._dapr_client is None:
            self._dapr_client = DaprClient()
        return self._dapr_client

    def withdraw(
        self,
        id_type: str,
        id_value: str,
        amount: float,
        currency: str,
        transfer_id: str,
        bank: str | None = None,
    ):
        payload = {
            "payer": {"partyIdType": id_type, "partyIdentifier": id_value},
            "amount": {"amount": str(amount), "currency": currency},
            "transferId": transfer_id,
            "bank": bank,
        }

        logger.info(f"Invoking core banking withdraw: {payload}")

        resp = self.dapr_client.invoke_method(
            config.CORE_BANKING_CONNECT_DAPR_ID,
            "transfers/withdraw",
            json.dumps(payload).encode("utf-8"),
            http_verb="POST",
        )

        try:
            body = (
                resp.decode("utf-8") if isinstance(resp, (bytes, bytearray)) else resp
            )
            return json.loads(body) if body else {}
        except Exception:
            return {}

    def deposit(
        self,
        id_type: str,
        id_value: str,
        amount: float,
        currency: str,
        source: str | None,
        transaction_id: str,
    ):
        payload = {
            "payee": {"partyIdType": id_type, "partyIdentifier": id_value},
            "amount": {"amount": str(amount), "currency": currency},
            "source": source,
            "transaction_id": transaction_id,
        }

        logger.info(f"Invoking core banking deposit: {payload}")

        resp = self.dapr_client.invoke_method(
            config.CORE_BANKING_CONNECT_DAPR_ID,
            "transfers/deposit",
            json.dumps(payload).encode("utf-8"),
            http_verb="POST",
        )

        try:
            body = (
                resp.decode("utf-8") if isinstance(resp, (bytes, bytearray)) else resp
            )
            return json.loads(body) if body else {}
        except Exception:
            return {}


core_banking_adapter = CoreBankingAdapter()
