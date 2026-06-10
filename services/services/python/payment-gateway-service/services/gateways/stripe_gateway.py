import abc
import json
import httpx
import time
import hmac
import hashlib
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Type
from . import stripe_gateway_impl

# --- Base Classes and Exceptions ---

class PaymentGatewayError(Exception):
    """Base exception for all payment gateway errors."""
    pass

class GatewayAPIError(PaymentGatewayError):
    """Raised for errors returned by the payment gateway's API."""
    def __init__(self, message: str, status_code: int, response_data: Dict[str, Any]) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class WebhookVerificationError(PaymentGatewayError):
    """Raised when a webhook signature verification fails."""
    pass

class BasePaymentGateway(abc.ABC):
    """
    Abstract base class for all payment gateway integrations.
    All concrete gateway implementations must inherit from this class.
    """

    @property
    @abc.abstractmethod
    def gateway_name(self) -> str:
        """The human-readable name of the payment gateway."""
        raise RuntimeError(f"Method not implemented - use the concrete gateway implementation")

    @property
    @abc.abstractmethod
    def supported_currencies(self) -> List[str]:
        """A list of ISO 4217 currency codes supported by this gateway."""
        raise RuntimeError(f"Method not implemented - use the concrete gateway implementation")

    @abc.abstractmethod
    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Creates a new payment intent.

        :param amount: The amount to charge (in the smallest currency unit, e.g., cents).
        :param currency: The three-letter ISO 4217 currency code.
        :param customer_id: Optional ID of the customer.
        :param metadata: Optional dictionary of key-value pairs to store.
        :return: A dictionary containing the payment intent details.
        """
        raise RuntimeError(f"Method not implemented - use the concrete gateway implementation")

    @abc.abstractmethod
    async def confirm_payment_intent(
        self,
        payment_intent_id: str,
        payment_method_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Confirms a payment intent, typically after a client-side action.

        :param payment_intent_id: The ID of the payment intent to confirm.
        :param payment_method_id: Optional ID of the payment method to use.
        :return: A dictionary containing the updated payment intent details.
        """
        # Delegated to stripe_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.stripe_gateway_impl'); return await getattr(_m, 'confirm_payment_intent')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    async def retrieve_payment_intent(
        self,
        payment_intent_id: str
    ) -> Dict[str, Any]:
        """
        Retrieves the details of a payment intent.

        :param payment_intent_id: The ID of the payment intent.
        :return: A dictionary containing the payment intent details.
        """
        # Delegated to stripe_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.stripe_gateway_impl'); return await getattr(_m, 'retrieve_payment_intent')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    async def process_webhook(
        self,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Processes an incoming webhook event, including signature verification.

        :param payload: The raw body of the webhook request.
        :param headers: The headers of the webhook request.
        :return: A dictionary representing the verified and parsed webhook event.
        :raises WebhookVerificationError: If signature verification fails.
        """
        # Delegated to stripe_gateway_impl
        import importlib; _m = importlib.import_module(f'services.gateways.stripe_gateway_impl'); return await getattr(_m, 'process_webhook')(**{k: v for k, v in locals().items() if k != 'self'})

    @abc.abstractmethod
    async def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refunds a previously successful payment.

        :param payment_intent_id: The ID of the payment intent to refund.
        :param amount: The amount to refund (in the smallest currency unit). Full refund if None.
        :param reason: The reason for the refund.
        :return: A dictionary containing the refund details.
        """
        raise RuntimeError(f"Method not implemented - use the concrete gateway implementation")

# --- Utility Functions for Retry Logic ---

def async_retry(
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (httpx.ConnectError, httpx.TimeoutException)
) -> None:
    """
    A decorator for retrying async functions with exponential backoff.
    """
    def decorator(func) -> None:
        async def wrapper(*args, **kwargs) -> None:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    # In a production environment, this should use a proper logger
                    # print(f"Attempt {attempt + 1} failed with {type(e).__name__}. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

# --- Stripe Gateway Implementation ---

class StripeGateway(BasePaymentGateway):
    """
    Stripe (International - cards, bank transfers) payment gateway implementation.
    Uses the Stripe REST API directly with httpx for full async support.
    
    This implementation uses the Payment Intents API for modern payment flow management.
    It includes:
    - Async API calls using httpx.
    - Retry logic with exponential backoff for transient network/timeout errors.
    - Proper error handling by raising custom exceptions.
    - Webhook signature verification.
    - Support for multiple African currencies as requested.
    """

    def __init__(self, api_key: str, webhook_secret: str, api_base_url: str = "https://api.stripe.com/v1") -> None:
        """
        Initializes the Stripe Gateway.

        :param api_key: Your Stripe secret API key (sk_live_... or sk_test_...).
        :param webhook_secret: Your Stripe webhook signing secret (whsec_...).
        :param api_base_url: The base URL for the Stripe API.
        """
        self._api_key = api_key
        self._webhook_secret = webhook_secret
        self._api_base_url = api_base_url
        self._client = httpx.AsyncClient(
            base_url=self._api_base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                # Stripe uses x-www-form-urlencoded for most POST requests
                "Content-Type": "application/x-www-form-urlencoded" 
            },
            timeout=30.0 # Default timeout for all requests
        )

    @property
    def gateway_name(self) -> str:
        """The human-readable name of the payment gateway."""
        return "Stripe (International - cards, bank transfers)"

    @property
    def supported_currencies(self) -> List[str]:
        """
        A list of African ISO 4217 currency codes supported by Stripe.
        This list is a representative subset of currencies Stripe supports globally.
        """
        # A representative list of African currencies supported by Stripe
        return ["ZAR", "KES", "NGN", "GHS", "EGP", "MAD", "MUR", "UGX", "TZS"]

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handles the HTTP response from the Stripe API, raising an exception on error.
        """
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            # Handle non-JSON responses (e.g., 500 errors from Stripe)
            response_data = {"error": {"message": f"Invalid JSON response from Stripe. Raw content: {response.text[:100]}..."}}

        if response.is_error:
            # Stripe error format is usually {"error": {"type": "...", "message": "..."}}
            error_message = response_data.get("error", {}).get("message", f"Stripe API error with status {response.status_code}")
            raise GatewayAPIError(
                message=error_message,
                status_code=response.status_code,
                response_data=response_data
            )
        return response_data

    @async_retry(max_retries=5, exceptions=(httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError))
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal POST request helper with retry logic."""
        # httpx automatically handles form-encoding for the 'data' parameter
        response = await self._client.post(endpoint, data=data)
        return self._handle_response(response)

    @async_retry(max_retries=5, exceptions=(httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError))
    async def _get(self, endpoint: str) -> Dict[str, Any]:
        """Internal GET request helper with retry logic."""
        response = await self._client.get(endpoint)
        return self._handle_response(response)

    # --- Abstract Method Implementations ---

    async def create_payment_intent(
        self,
        amount: int,
        currency: str,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Creates a new Stripe PaymentIntent.

        :param amount: The amount to charge (in the smallest currency unit, e.g., cents).
        :param currency: The three-letter ISO 4217 currency code.
        :param customer_id: Optional ID of the customer.
        :param metadata: Optional dictionary of key-value pairs to store.
        :return: A dictionary containing the PaymentIntent details.
        :raises GatewayAPIError: If the Stripe API returns an error.
        :raises ValueError: If the currency is not supported.
        """
        currency = currency.upper()
        if currency not in self.supported_currencies and currency not in ["USD", "EUR", "GBP"]: # Allow common international currencies too
            raise ValueError(f"Currency {currency} is not explicitly supported by this gateway instance.")

        data = {
            "amount": amount,
            "currency": currency.lower(), # Stripe expects lowercase currency
            # Default payment method types for international cards and bank transfers
            "payment_method_types[]": ["card", "customer_balance"], 
            "capture_method": "automatic",
        }
        if customer_id:
            data["customer"] = customer_id
        if metadata:
            # Stripe expects metadata keys to be simple strings
            for k, v in metadata.items():
                data[f"metadata[{k}]"] = str(v)

        # Add any extra kwargs as top-level parameters
        data.update(kwargs)

        return await self._post("/payment_intents", data=data)

    async def confirm_payment_intent(
        self,
        payment_intent_id: str,
        payment_method_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Confirms a Stripe PaymentIntent.

        :param payment_intent_id: The ID of the PaymentIntent to confirm.
        :param payment_method_id: Optional ID of the PaymentMethod to use.
        :return: A dictionary containing the updated PaymentIntent details.
        :raises GatewayAPIError: If the Stripe API returns an error.
        """
        endpoint = f"/payment_intents/{payment_intent_id}/confirm"
        data = {}
        if payment_method_id:
            data["payment_method"] = payment_method_id
        
        data.update(kwargs)

        return await self._post(endpoint, data=data)

    async def retrieve_payment_intent(
        self,
        payment_intent_id: str
    ) -> Dict[str, Any]:
        """
        Retrieves the details of a Stripe PaymentIntent.

        :param payment_intent_id: The ID of the PaymentIntent.
        :return: A dictionary containing the PaymentIntent details.
        :raises GatewayAPIError: If the Stripe API returns an error.
        """
        endpoint = f"/payment_intents/{payment_intent_id}"
        return await self._get(endpoint)

    async def process_webhook(
        self,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Processes an incoming Stripe webhook event, including signature verification.

        :param payload: The raw body of the webhook request.
        :param headers: The headers of the webhook request.
        :return: A dictionary representing the verified and parsed webhook event.
        :raises WebhookVerificationError: If signature verification fails.
        """
        signature = headers.get("stripe-signature")
        if not signature:
            raise WebhookVerificationError("Missing Stripe-Signature header.")

        # The header value is a comma-separated list of key-value pairs
        # e.g., t=1600000000,v1=5257...
        try:
            # Parse the timestamp and signature parts
            parts = {
                k: v for k, v in [part.split("=") for part in signature.split(",")]
            }
            timestamp = int(parts.get("t"))
            signature_v1 = parts.get("v1")
        except (ValueError, AttributeError, TypeError):
            raise WebhookVerificationError("Invalid Stripe-Signature format.")

        if not timestamp or not signature_v1:
            raise WebhookVerificationError("Missing timestamp or v1 signature in Stripe-Signature header.")

        # 1. Check timestamp
        tolerance = 300 # 5 minutes
        if abs(time.time() - timestamp) > tolerance:
            raise WebhookVerificationError("Webhook timestamp is outside the tolerance window.")

        # 2. Prepare signed payload
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"

        # 3. Compute expected signature
        expected_signature = hmac.new(
            self._webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 4. Compare signatures
        # Use hmac.compare_digest for constant-time comparison to mitigate timing attacks
        if not hmac.compare_digest(expected_signature, signature_v1):
            raise WebhookVerificationError("Webhook signature verification failed.")

        # 5. Return the parsed event
        try:
            return json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            raise WebhookVerificationError("Invalid JSON payload.")

    async def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refunds a previously successful payment associated with a PaymentIntent.
        Stripe's API requires creating a Refund object, which references a Charge.
        We first retrieve the PaymentIntent to get the Charge ID.

        :param payment_intent_id: The ID of the PaymentIntent to refund.
        :param amount: The amount to refund (in the smallest currency unit). Full refund if None.
        :param reason: The reason for the refund (e.g., 'duplicate', 'fraudulent', 'requested_by_customer').
        :return: A dictionary containing the Refund details.
        :raises GatewayAPIError: If the Stripe API returns an error.
        """
        # 1. Retrieve the PaymentIntent to get the Charge ID
        intent = await self.retrieve_payment_intent(payment_intent_id)
        # The latest_charge field holds the ID of the Charge object created by the PaymentIntent
        charge_id = intent.get("latest_charge")

        if not charge_id:
            raise GatewayAPIError(
                message=f"Could not find a successful charge for PaymentIntent {payment_intent_id}. Cannot process refund.",
                status_code=400,
                response_data={"intent": intent}
            )

        # 2. Create the Refund
        data = {
            "charge": charge_id,
        }
        if amount is not None:
            data["amount"] = amount
        if reason:
            data["reason"] = reason
        
        data.update(kwargs)

        return await self._post("/refunds", data=data)
