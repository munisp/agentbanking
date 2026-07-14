import abc
import json
import time
import hmac
import hashlib
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx import AsyncClient, HTTPStatusError, ConnectError, TimeoutException

# --- BasePaymentGateway Abstract Class ---

class BasePaymentGateway(abc.ABC):
    """
    Abstract base class for all payment gateway integrations.
    Defines the core methods that every gateway must implement.
    """

    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        """
        Initializes the gateway with necessary credentials and base URL.
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url

    @abc.abstractmethod
    async def initialize_payment(self, amount: float, currency: str, customer_info: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Initiates a payment transaction.

        :param amount: The transaction amount.
        :param currency: The currency code (e.g., 'NGN', 'USD').
        :param customer_info: Dictionary containing customer details (e.g., email, name).
        :param metadata: Optional dictionary for custom transaction data.
        :return: A dictionary containing the payment initiation response, typically including a redirect URL.
        """
        # Delegated to flutterwave_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.flutterwave_gateway_impl'); return await getattr(_m, 'initialize_payment')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    async def verify_payment(self, transaction_reference: str) -> Dict[str, Any]:
        """
        Verifies the status of a completed transaction using its reference.

        :param transaction_reference: The unique reference ID for the transaction.
        :return: A dictionary containing the transaction verification details.
        """
        # Delegated to flutterwave_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.flutterwave_gateway_impl'); return await getattr(_m, 'verify_payment')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    async def process_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """
        Processes an incoming webhook notification, including signature verification.

        :param headers: The HTTP headers of the incoming webhook request.
        :param body: The raw body of the incoming webhook request.
        :return: A dictionary containing the processed webhook data.
        """
        # Delegated to flutterwave_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.flutterwave_gateway_impl'); return await getattr(_m, 'process_webhook')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    async def refund_payment(self, transaction_reference: str, amount: float) -> Dict[str, Any]:
        """
        Initiates a refund for a successful transaction.

        :param transaction_reference: The unique reference ID of the original transaction.
        :param amount: The amount to be refunded.
        :return: A dictionary containing the refund initiation response.
        """
        # Delegated to flutterwave_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.flutterwave_gateway_impl'); return await getattr(_m, 'refund_payment')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    def get_supported_currencies(self) -> List[str]:
        """
        Returns a list of supported currency codes for this gateway.
        """
        raise RuntimeError(f"Method not implemented - use the concrete gateway implementation")

# --- FlutterwaveGateway Implementation ---

class FlutterwaveGateway(BasePaymentGateway):
    """
    Payment gateway integration for Flutterwave (Rave).
    Supports various payment methods across Africa.
    """

    # Key African currencies and others commonly supported by Flutterwave
    SUPPORTED_CURRENCIES = [
        "NGN", "GHS", "KES", "ZAR", "UGX", "TZS", "XOF", "XAF", "RWF", "ZMW",
        "USD", "EUR", "GBP", "CAD"
    ]
    
    # Flutterwave API Endpoints
    BASE_URL = "https://api.flutterwave.com/v3"
    INITIATE_ENDPOINT = "/payments"
    VERIFY_ENDPOINT = "/transactions/{id}/verify"
    REFUND_ENDPOINT = "/refunds"
    
    # Webhook header for signature verification
    WEBHOOK_SIGNATURE_HEADER = "verif-hash"

    def __init__(self, secret_key: str, webhook_secret_hash: str, is_live: bool = False) -> None:
        """
        Initializes the Flutterwave Gateway.

        :param secret_key: Your Flutterwave Secret Key (used for Authorization header).
        :param webhook_secret_hash: The Secret Hash set on your Flutterwave dashboard for webhook verification.
        :param is_live: Boolean to determine if the live or staging environment should be used.
        """
        # Flutterwave uses a single Secret Key for API calls, and a separate Secret Hash for webhooks.
        # We use the secret_key for the BasePaymentGateway's secret_key attribute.
        super().__init__(api_key="", secret_key=secret_key, base_url=self.BASE_URL)
        self.webhook_secret_hash = webhook_secret_hash
        self.client = self._get_async_client()

    def _get_async_client(self) -> AsyncClient:
        """
        Creates and configures an httpx.AsyncClient with default headers and timeout.
        """
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        # Use a longer timeout for external API calls
        return AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Generic method to handle API requests, including retry logic and error handling.
        """
        max_retries = 3
        delay = 1  # Initial delay in seconds

        for attempt in range(max_retries):
            try:
                response = await self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response.json()
            except HTTPStatusError as e:
                # Handle specific HTTP errors (e.g., 400, 401, 404, 500)
                error_detail = e.response.json() if e.response.content else {"message": "No response content"}
                if 400 <= e.response.status_code < 500 and e.response.status_code not in [429, 503]:
                    # Client error (e.g., bad request, unauthorized) - do not retry
                    raise ValueError(f"Flutterwave API Client Error ({e.response.status_code}): {error_detail.get('message', str(error_detail))}") from e
                
                # Server error or rate limit - potentially retry
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed with status {e.response.status_code}. Retrying in {delay}s...")
                    # Note: In a real application, you would not close the client here, but rather
                    # ensure the client is properly managed. For this isolated example, we simulate
                    # a brief pause.
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise RuntimeError(f"Flutterwave API Server Error ({e.response.status_code}) after {max_retries} attempts: {error_detail.get('message', str(error_detail))}") from e
            except (ConnectError, TimeoutException) as e:
                # Network or timeout error - retry
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed with network error. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise ConnectionError(f"Flutterwave API Connection failed after {max_retries} attempts: {e}") from e
            except Exception as e:
                # Catch all other exceptions
                raise RuntimeError(f"An unexpected error occurred during API request: {e}") from e
        
        # Should be unreachable, but for completeness
        raise RuntimeError("Request failed after all retries.")

    async def initialize_payment(self, amount: float, currency: str, customer_info: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Initiates a payment transaction using the standard Flutterwave V3 /payments endpoint.
        This typically returns a link to the Flutterwave payment page.

        :param amount: The transaction amount.
        :param currency: The currency code (e.g., 'NGN', 'USD').
        :param customer_info: Dictionary containing customer details (email, name, phone_number).
        :param metadata: Optional dictionary for custom transaction data.
        :return: A dictionary containing the payment initiation response.
        :raises ValueError: If required customer information is missing or currency is unsupported.
        """
        if currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {currency}. Supported currencies are: {', '.join(self.SUPPORTED_CURRENCIES)}")
        
        required_customer_keys = ["email", "name", "phone_number"]
        if not all(key in customer_info for key in required_customer_keys):
            raise ValueError(f"Missing required customer info keys. Required: {', '.join(required_customer_keys)}")

        # Generate a unique transaction reference
        tx_ref = f"TX-{int(time.time() * 1000)}"

        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount),
            "currency": currency,
            "redirect_url": "https://your-success-url.com/payment-callback", # MUST be replaced with a real URL
            "customer": customer_info,
            "customizations": {
                "title": "Payment for Goods/Services",
                "logo": "https://your-logo-url.com/logo.png"
            },
            "meta": metadata or {}
        }

        response = await self._make_request(
            method="POST",
            endpoint=self.INITIATE_ENDPOINT,
            json=payload
        )
        
        if response.get("status") == "success" and response.get("data", {}).get("link"):
            return {
                "status": "success",
                "transaction_reference": tx_ref,
                "payment_link": response["data"]["link"],
                "raw_response": response
            }
        
        raise RuntimeError(f"Payment initialization failed: {response.get('message', 'Unknown error')}")

    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verifies the status of a completed transaction using its Flutterwave transaction ID.
        Note: Flutterwave recommends verifying the transaction ID (`id` from the webhook/callback data),
        not the merchant's `tx_ref`.

        :param transaction_id: The unique Flutterwave ID for the transaction.
        :return: A dictionary containing the transaction verification details.
        :raises ValueError: If the verification fails or the transaction is not found.
        """
        endpoint = self.VERIFY_ENDPOINT.format(id=transaction_id)
        
        response = await self._make_request(
            method="GET",
            endpoint=endpoint
        )

        if response.get("status") == "success" and response.get("data"):
            data = response["data"]
            return {
                "status": data.get("status"), # e.g., 'successful', 'pending', 'failed'
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "transaction_id": data.get("id"),
                "tx_ref": data.get("tx_ref"),
                "raw_response": response
            }
        
        raise ValueError(f"Transaction verification failed: {response.get('message', 'Transaction not found or unknown error')}")

    def _verify_webhook_signature(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verifies the authenticity of the webhook request using the secret hash.

        :param headers: The HTTP headers of the incoming webhook request.
        :param body: The raw body of the incoming webhook request.
        :return: True if the signature is valid, False otherwise.
        """
        # Flutterwave sends the secret hash in the header.
        # The body is hashed using HMAC-SHA256 with the secret hash as the key.
        # The result of the hash is then compared to the value of the 'verif-hash' header.
        
        # 1. Get the expected signature from the header
        # Header name is case-insensitive, so we normalize the keys
        header_keys = {k.lower(): v for k, v in headers.items()}
        received_hash = header_keys.get(self.WEBHOOK_SIGNATURE_HEADER.lower())

        if not received_hash:
            print("Webhook verification failed: Missing verif-hash header.")
            return False

        # 2. Compute the expected hash
        # The key for HMAC is the webhook_secret_hash set on the dashboard
        # The message is the raw request body
        
        try:
            # The key must be bytes
            key = self.webhook_secret_hash.encode('utf-8')
            
            # Compute the HMAC-SHA256 hash
            computed_hash = hmac.new(
                key=key,
                msg=body,
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # 3. Compare the computed hash with the received hash
            # Use hmac.compare_digest for constant-time comparison to mitigate timing attacks
            is_valid = hmac.compare_digest(computed_hash, received_hash)
            
            if not is_valid:
                print(f"Webhook verification failed: Computed hash {computed_hash} != Received hash {received_hash}")
            
            return is_valid

        except Exception as e:
            print(f"Error during webhook signature computation: {e}")
            return False

    async def process_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """
        Processes an incoming webhook notification, including signature verification.
        
        :param headers: The HTTP headers of the incoming webhook request.
        :param body: The raw body of the incoming webhook request.
        :return: A dictionary containing the processed webhook data.
        :raises SecurityError: If the webhook signature verification fails.
        :raises ValueError: If the body is not valid JSON.
        """
        if not self._verify_webhook_signature(headers, body):
            raise SecurityError("Webhook signature verification failed. Request is not from Flutterwave.")

        try:
            # The body is expected to be a JSON string
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON body in webhook request: {e}")

        # Flutterwave recommends verifying the transaction via API after receiving a successful webhook
        # We will return the data and let the calling application handle the final verification step
        # using the `verify_payment` method, as per best practice.
        
        event_type = data.get("event")
        transaction_data = data.get("data", {})
        
        return {
            "event": event_type,
            "transaction_id": transaction_data.get("id"),
            "tx_ref": transaction_data.get("tx_ref"),
            "status": transaction_data.get("status"),
            "raw_data": data
        }

    async def refund_payment(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        """
        Initiates a refund for a successful transaction using the Flutterwave transaction ID.

        :param transaction_id: The unique Flutterwave ID of the original transaction.
        :param amount: The amount to be refunded.
        :return: A dictionary containing the refund initiation response.
        :raises ValueError: If the transaction ID is invalid or the refund fails.
        """
        if amount <= 0:
            raise ValueError("Refund amount must be greater than zero.")

        payload = {
            "transaction_id": transaction_id,
            "amount": amount
        }

        response = await self._make_request(
            method="POST",
            endpoint=self.REFUND_ENDPOINT,
            json=payload
        )

        if response.get("status") == "success" and response.get("data"):
            data = response["data"]
            return {
                "status": data.get("status"), # e.g., 'successful', 'pending'
                "reference": data.get("reference"),
                "raw_response": response
            }
        
        raise ValueError(f"Refund failed: {response.get('message', 'Unknown error')}")

    def get_supported_currencies(self) -> List[str]:
        """
        Returns a list of supported currency codes for this gateway.
        """
        return self.SUPPORTED_CURRENCIES

# --- Custom Exception for Security ---

class SecurityError(Exception):
    """Custom exception for security-related failures, like webhook signature mismatch."""
    pass

# --- Production implementation imported ---
from .flutterwave_gateway_full import FlutterwaveGateway as FlutterwaveGatewayProduction  # noqa: F401
from . import flutterwave_gateway_impl
