import json

from dapr.clients import DaprClient

from utils import get_config, create_logger

config = get_config()
logger = create_logger(__name__)


class PaymentRailsConnectorAdapter:
    def __init__(self):
        self._dapr_client = None

    @property
    def dapr_client(self):
        if self._dapr_client is None:
            self._dapr_client = DaprClient()
        return self._dapr_client

    def initiate_outbound_transfer(self, payload: dict):
        logger.info(f"Invoking payment rails outbound transfer: {payload}")

        resp = self.dapr_client.invoke_method(
            config.PAYMENT_RAILS_CONNECTORS_DAPR_ID,
            "outbound/transfers",
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


payment_rails_connector_adapter = PaymentRailsConnectorAdapter()
