from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context

logger = create_logger(__name__)
config = get_config()


class ExchangeRateServiceAdapter(ExternalAPIClient):
    """Exchange rate service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.EXCHANGE_RATE_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def get_exchange_rate(self, from_currency: str, to_currency: str, context: Context):
        """Get an exchange rate for a currency pair."""
        from_currency = str(from_currency).upper()
        to_currency = str(to_currency).upper()

        if from_currency == to_currency:
            return {
                "base_currency": from_currency,
                "quote_currency": to_currency,
                "rate": 1.0,
            }

        headers = {
            "x-tenant-id": context.tenant_id,
        }

        response = self._get(
            endpoint="/exchange-rates",
            params={"from": from_currency, "to": to_currency},
            headers=headers,
        )

        if isinstance(response, list) and len(response) > 0:
            return response[0]

        inverse_response = self._get(
            endpoint="/exchange-rates",
            params={"from": to_currency, "to": from_currency},
            headers=headers,
        )

        if isinstance(inverse_response, list) and len(inverse_response) > 0:
            inverse_rate_payload = inverse_response[0]
            inverse_rate = float((inverse_rate_payload or {}).get("rate", 0))
            if inverse_rate <= 0:
                raise Exception(
                    f"Invalid inverse exchange rate for {to_currency}/{from_currency}"
                )

            return {
                **inverse_rate_payload,
                "base_currency": from_currency,
                "quote_currency": to_currency,
                "rate": 1 / inverse_rate,
                "derived_from_inverse": True,
            }

        raise Exception(f"Exchange rate not found for {from_currency}/{to_currency}")
