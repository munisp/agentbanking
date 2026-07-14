import abc
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx import AsyncClient, ConnectError, HTTPStatusError, TimeoutException

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Abstract Base Class ---

class BasePaymentGateway(abc.ABC):
    """
    Abstract base class for all payment gateway integrations.
    Defines the required interface for a production-ready gateway.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initializes the gateway with configuration.
        :param config: A dictionary containing gateway-specific configuration.
        """
        self.config = config
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")
        self.secret_key = config.get("secret_key")
        self.merchant_id = config.get("merchant_id")
        self.hash_key = config.get("hash_key")
        self.client: AsyncClient = self._init_http_client()

    def _init_http_client(self) -> AsyncClient:
        """Initializes and returns an httpx.AsyncClient with default settings."""
        return AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    @abc.abstractmethod
    async def create_payment_link(self, amount: float, currency: str, transaction_ref: str, customer_info: Dict[str, str], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Initiates a payment and returns a redirect URL or payment link.
        :param amount: The payment amount (in major unit, e.g., Naira).
        :param currency: The currency code (e.g., 'NGN').
        :param transaction_ref: A unique reference for the transaction.
        :param customer_info: Dictionary with customer details (e.g., 'email', 'name').
        :param metadata: Optional extra data to pass to the gateway.
        :return: A dictionary containing the payment link/redirect URL and transaction details.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def verify_transaction(self, transaction_ref: str, amount: float, currency: str) -> Dict[str, Any]:
        """
        Verifies the status of a transaction using its reference.
        :param transaction_ref: The unique reference of the transaction.
        :param amount: The expected amount of the transaction (in major unit).
        :param currency: The expected currency of the transaction.
        :return: A dictionary containing the transaction status and details.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def handle_webhook(self, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming webhook notification and verifies its signature.
        :param headers: The HTTP headers of the webhook request.
        :param body: The JSON/form body of the webhook request.
        :return: A dictionary containing the processed webhook data and status.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_supported_currencies(self) -> List[str]:
        """
        Returns a list of supported currency codes.
        :return: A list of currency codes (e.g., ['NGN', 'USD']).
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _to_minor_unit(self, amount: float) -> int:
        """
        Converts a major unit amount (e.g., Naira) to its minor unit (e.g., Kobo).
        :param amount: Amount in major unit.
        :return: Amount in minor unit (integer).
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _get_currency_code(self, currency: str) -> str:
        """
        Converts a 3-letter currency code (e.g., 'NGN') to the gateway's numeric code.
        :param currency: 3-letter currency code.
        :return: Gateway's numeric currency code (string).
        """
        raise NotImplementedError

    async def __aenter__(self):
        """Context manager entry point."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point, closes the HTTP client."""
        await self.client.aclose()

# --- Utility Functions ---

def _retry_on_exception(max_retries: int = 3, backoff_factor: float = 0.5) -> None:
    """Decorator for retrying async functions on specific HTTP/connection exceptions."""
    def decorator(func) -> None:
        async def wrapper(self, *args, **kwargs) -> None:
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except (ConnectError, TimeoutException, HTTPStatusError) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    
                    # Check for specific HTTP status codes that should not be retried (e.g., 4xx client errors)
                    if isinstance(e, HTTPStatusError) and 400 <= e.response.status_code < 500 and e.response.status_code != 408:
                        logger.error(f"Non-retryable client error {e.response.status_code} for {func.__name__}: {e}")
                        raise

                    delay = backoff_factor * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}. Retrying in {delay:.2f}s...")
                    import asyncio
                    await asyncio.sleep(delay)
        return wrapper
    return decorator

# --- GTPay Gateway Implementation ---

class GTPayGateway(BasePaymentGateway):
    """
    A complete, production-ready Python implementation for the GTPay (GTBank)
    payment gateway integration.

    GTPay uses a form-based redirect for payment initiation and a separate
    JSON API for transaction status verification (requery).
    Authentication is based on SHA512 hashing with a secret hash key.
    """

    # GTPay Endpoints
    TRANSACTION_URL = "https://ibank.gtbank.com/GTPay/Tranx.aspx"
    REQUERY_URL = "https://ibank.gtbank.com/GTPayService/gettransactionstatus.json"

    # GTPay Numeric Currency Codes
    CURRENCY_MAP = {
        "NGN": "566",  # Nigerian Naira
        "USD": "840",  # US Dollar (Documentation mentioned 826, but 840 is standard ISO)
        # Assuming other major African currencies might be supported if GTBank supports them
        # but sticking to documented ones for a production-ready implementation.
    }
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initializes the GTPay gateway.
        :param config: Must contain 'merchant_id' and 'hash_key'.
        """
        # GTPay is primarily a redirect-based gateway, so the base_url for the
        # AsyncClient is set to the requery endpoint for API calls.
        config["base_url"] = self.REQUERY_URL
        super().__init__(config)
        
        if not self.merchant_id or not self.hash_key:
            raise ValueError("GTPay configuration must include 'merchant_id' and 'hash_key'.")

    def _init_http_client(self) -> AsyncClient:
        """Initializes and returns an httpx.AsyncClient for the REQUERY API."""
        # For GTPay, the client is mainly used for the REQUERY API.
        return AsyncClient(
            timeout=10.0,
            headers={"Content-Type": "application/json"},
        )

    def _to_minor_unit(self, amount: float) -> int:
        """
        Converts a major unit amount (e.g., Naira) to its minor unit (e.g., Kobo).
        GTPay expects the amount in the smallest unit (kobo/cents).
        """
        return int(round(amount * 100))

    def _get_currency_code(self, currency: str) -> str:
        """
        Converts a 3-letter currency code (e.g., 'NGN') to the gateway's numeric code.
        """
        currency = currency.upper()
        if currency not in self.CURRENCY_MAP:
            raise ValueError(f"Unsupported currency: {currency}. Supported: {list(self.CURRENCY_MAP.keys())}")
        return self.CURRENCY_MAP[currency]

    def _generate_payment_hash(self, tranx_id: str, amount_minor: int, currency_code: str, noti_url: str, cust_id: str) -> str:
        """
        Generates the SHA512 hash for the payment initiation request.
        Hash is: SHA512(gtpay_mert_id + gtpay_tranx_id + gtpay_tranx_amt + gtpay_tranx_curr + gtpay_cust_id + gtpay_tranx_noti_url + hashkey)
        """
        hash_string = (
            f"{self.merchant_id}"
            f"{tranx_id}"
            f"{amount_minor}"
            f"{currency_code}"
            f"{cust_id}"
            f"{noti_url}"
            f"{self.hash_key}"
        )
        return hashlib.sha512(hash_string.encode('utf-8')).hexdigest()

    def _generate_requery_hash(self, tranx_id: str) -> str:
        """
        Generates the SHA512 hash for the transaction status requery request.
        Hash is: SHA512(mertid + tranxid + hashkey)
        """
        hash_string = (
            f"{self.merchant_id}"
            f"{tranx_id}"
            f"{self.hash_key}"
        )
        return hashlib.sha512(hash_string.encode('utf-8')).hexdigest()

    async def create_payment_link(self, amount: float, currency: str, transaction_ref: str, customer_info: Dict[str, str], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Initiates a payment by preparing the parameters for a redirect/form submission.
        GTPay does not have a direct API for this; it requires a form POST to their URL.
        The returned dictionary contains the URL and the POST data.
        """
        try:
            amount_minor = self._to_minor_unit(amount)
            currency_code = self._get_currency_code(currency)
            
            # Required parameters
            customer_id = customer_info.get("id", customer_info.get("email", "N/A"))
            notification_url = self.config.get("notification_url")
            
            if not notification_url:
                raise ValueError("Configuration missing 'notification_url' for payment initiation.")

            # Generate the hash
            gtpay_hash = self._generate_payment_hash(
                tranx_id=transaction_ref,
                amount_minor=amount_minor,
                currency_code=currency_code,
                noti_url=notification_url,
                cust_id=customer_id
            )

            # Construct the POST data
            post_data = {
                "gtpay_mert_id": self.merchant_id,
                "gtpay_tranx_id": transaction_ref,
                "gtpay_tranx_amt": str(amount_minor),
                "gtpay_tranx_curr": currency_code,
                "gtpay_cust_id": customer_id,
                "gtpay_tranx_noti_url": notification_url,
                "gtpay_hash": gtpay_hash,
                "gtpay_tranx_memo": metadata.get("memo", "Online Payment") if metadata else "Online Payment",
                "gtpay_cust_name": customer_info.get("name", "Customer"),
                # Optional: Add other optional parameters from metadata if needed
            }

            return {
                "status": "success",
                "redirect_url": self.TRANSACTION_URL,
                "post_data": post_data,
                "message": "Payment parameters prepared for form submission/redirect."
            }

        except ValueError as e:
            logger.error(f"Validation error in create_payment_link: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in create_payment_link: {e}")
            return {"status": "error", "message": "An unexpected error occurred during payment link creation."}

    @_retry_on_exception(max_retries=3)
    async def verify_transaction(self, transaction_ref: str, amount: float, currency: str) -> Dict[str, Any]:
        """
        Verifies the status of a transaction using the GTPay Requery API.
        """
        try:
            amount_minor = self._to_minor_unit(amount)
            
            # Generate the requery hash
            requery_hash = self._generate_requery_hash(tranx_id=transaction_ref)

            # Construct the request payload
            payload = {
                "mertid": self.merchant_id,
                "amount": str(amount_minor),
                "tranxid": transaction_ref,
                "hash": requery_hash,
            }

            # GTPay Requery API is a POST request
            response = await self.client.post(self.REQUERY_URL, json=payload)
            response.raise_for_status() # Raise for bad status codes (4xx or 5xx)

            data = response.json()
            
            # Check for successful response code from GTPay (e.g., '00')
            response_code = data.get("ResponseCode")
            
            if response_code == "00":
                status = "success"
                message = data.get("ResponseDescription", "Transaction Approved")
            elif response_code in ["01", "02", "03", "04", "05", "06", "07", "08", "09"]:
                # Example of common error codes (01-09 are often bank errors)
                status = "failed"
                message = data.get("ResponseDescription", "Transaction Failed")
            else:
                status = "pending"
                message = data.get("ResponseDescription", "Unknown Status")

            return {
                "status": status,
                "message": message,
                "gateway_data": data,
                "transaction_ref": transaction_ref,
                "amount": amount,
                "currency": currency,
            }

        except HTTPStatusError as e:
            logger.error(f"HTTP error during transaction verification for {transaction_ref}: {e.response.status_code} - {e.response.text}")
            return {"status": "error", "message": f"API HTTP Error: {e.response.status_code}", "details": e.response.text}
        except (ConnectError, TimeoutException) as e:
            logger.error(f"Connection/Timeout error during transaction verification for {transaction_ref}: {e}")
            return {"status": "error", "message": f"Network Error: {type(e).__name__}"}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response during transaction verification for {transaction_ref}: {response.text}")
            return {"status": "error", "message": "Invalid response from gateway."}
        except Exception as e:
            logger.error(f"Unexpected error during transaction verification for {transaction_ref}: {e}")
            return {"status": "error", "message": f"Unexpected Error: {str(e)}"}

    def _verify_webhook_hash(self, tranx_id: str, amount_minor: int, status_code: str, currency_code: str, received_hash: str) -> bool:
        """
        Verifies the hash received in the webhook notification.
        Hash is: SHA512(gtpay_tranx_id + gtpay_tranx_amt_small_denom + gtpay_tranx_status_code + gtpay_tranx_curr + hashkey)
        """
        hash_string = (
            f"{tranx_id}"
            f"{amount_minor}"
            f"{status_code}"
            f"{currency_code}"
            f"{self.hash_key}"
        )
        computed_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest()
        
        # Case-insensitive comparison is safer for hashes
        return computed_hash.lower() == received_hash.lower()

    def handle_webhook(self, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming GTPay webhook notification and verifies its signature.
        GTPay sends a POST request to the notification URL with form data.
        The body is expected to be a dictionary of the form data.
        """
        try:
            # Extract required parameters from the body
            tranx_id = body.get("gtpay_tranx_id")
            amount_minor_str = body.get("gtpay_tranx_amt_small_denom")
            status_code = body.get("gtpay_tranx_status_code")
            currency_code = body.get("gtpay_tranx_curr")
            received_hash = body.get("gtpay_full_verification_hash")

            if not all([tranx_id, amount_minor_str, status_code, currency_code, received_hash]):
                logger.warning(f"Missing required parameters in webhook body: {body}")
                return {"status": "error", "message": "Missing required webhook parameters for verification."}

            try:
                amount_minor = int(amount_minor_str)
            except ValueError:
                logger.error(f"Invalid amount_minor_str in webhook: {amount_minor_str}")
                return {"status": "error", "message": "Invalid amount format in webhook."}

            # 1. Verify the hash
            is_valid = self._verify_webhook_hash(
                tranx_id=tranx_id,
                amount_minor=amount_minor,
                status_code=status_code,
                currency_code=currency_code,
                received_hash=received_hash
            )

            if not is_valid:
                logger.error(f"Webhook signature verification failed for transaction {tranx_id}.")
                return {"status": "error", "message": "Webhook signature verification failed."}

            # 2. Process the notification
            if status_code == "00":
                status = "success"
                message = body.get("gtpay_tranx_status_desc", "Transaction Approved")
            else:
                status = "failed"
                message = body.get("gtpay_tranx_status_desc", "Transaction Failed")

            return {
                "status": "success",
                "message": message,
                "is_verified": True,
                "transaction_status": status,
                "transaction_ref": tranx_id,
                "amount_minor": amount_minor,
                "gateway_data": body,
            }

        except Exception as e:
            logger.error(f"Unexpected error in handle_webhook: {e}")
            return {"status": "error", "message": f"Unexpected error during webhook processing: {str(e)}"}

    async def get_supported_currencies(self) -> List[str]:
        """
        Returns a list of supported currency codes based on the internal map.
        """
        return list(self.CURRENCY_MAP.keys())

# --- Example Usage (for context, not part of the class) ---
# async def main():
#     config = {
#         "merchant_id": "YOUR_MERCHANT_ID",
#         "hash_key": "YOUR_SECRET_HASH_KEY",
#         "notification_url": "https://yourdomain.com/webhooks/gtpay",
#     }
#     
#     async with GTPayGateway(config) as gateway:
#         # 1. Create Payment Link
#         payment_details = await gateway.create_payment_link(
#             amount=1000.50, 
#             currency="NGN", 
#             transaction_ref="ORDER12345", 
#             customer_info={"email": "test@example.com", "name": "John Doe", "id": "CUST001"}
#         )
#         print(f"Payment Details: {payment_details}")
#         
#         # 2. Verify Transaction (Mocking a successful requery)
#         # Note: This will fail unless you have a live GTPay environment and a valid transaction ID
#         # verification_result = await gateway.verify_transaction(
#         #     transaction_ref="ORDER12345", 
#         #     amount=1000.50, 
#         #     currency="NGN"
#         # )
#         # print(f"Verification Result: {verification_result}")
#         
#         # 3. Handle Webhook (Mocking a webhook call)
#         # mock_webhook_body = {
#         #     "gtpay_tranx_id": "ORDER12345",
#         #     "gtpay_tranx_amt_small_denom": "100050",
#         #     "gtpay_tranx_status_code": "00",
#         #     "gtpay_tranx_curr": "566",
#         #     "gtpay_full_verification_hash": "...", # Must be calculated correctly
#         #     "gtpay_tranx_status_desc": "Approved by Financial Institution",
#         # }
#         # mock_headers = {}
#         # webhook_result = gateway.handle_webhook(mock_headers, mock_webhook_body)
#         # print(f"Webhook Result: {webhook_result}")
# 
# if __name__ == "__main__":
#     import asyncio
#     # asyncio.run(main())
#     pass

# --- Production implementation imported ---
from .gtpay_gateway_full import GtpayGateway as GtpayGatewayProduction  # noqa: F401
