import abc
import asyncio
import functools
import json
import hmac
import hashlib
from typing import Any, Dict, List, Optional, Callable, Awaitable, TypeVar

import httpx
from . import paystack_gateway_impl

# --- Custom Exceptions ---

class PaymentGatewayError(Exception):
    """Base exception for all payment gateway errors."""
    pass

class GatewayAPIError(PaymentGatewayError):
    """Exception raised for errors returned by the payment gateway API."""
    def __init__(self, message: str, status_code: int, response_data: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class GatewayConnectionError(PaymentGatewayError):
    """Exception raised for network or connection errors."""
    pass

class GatewayVerificationError(PaymentGatewayError):
    """Exception raised when a transaction verification fails."""
    pass

class GatewayWebhookError(PaymentGatewayError):
    """Base exception for webhook processing errors."""
    pass

class GatewaySignatureVerificationError(GatewayWebhookError):
    """Exception raised when a webhook signature verification fails."""
    pass

# --- Retry Logic with Exponential Backoff ---

R = TypeVar('R')

def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (GatewayConnectionError, GatewayAPIError),
) -> Callable[[Callable[..., Awaitable[R]]], Callable[..., Awaitable[R]]]:
    """
    A decorator to add exponential backoff and retry logic to async methods.
    """
    def decorator(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> R:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    
                    print(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            # This line should not be reached, but for type hinting completeness
            raise RuntimeError("Exceeded maximum retries.")

        return wrapper
    return decorator

# --- Abstract Base Class ---

class BasePaymentGateway(abc.ABC):
    """
    Abstract Base Class for all payment gateway implementations.
    All concrete gateway classes must inherit from this class and implement
    all abstract methods.
    """
    
    BASE_URL: str
    SUPPORTED_CURRENCIES: List[str]

    def __init__(self, secret_key: str, public_key: Optional[str] = None) -> None:
        """
        Initialize the gateway with necessary credentials.
        :param secret_key: The secret key for server-side operations.
        :param public_key: The public key for client-side operations (optional).
        """
        self._secret_key = secret_key
        self._public_key = public_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self._secret_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0 # Default timeout
        )

    @abc.abstractmethod
    async def initialize_transaction(
        self,
        amount: int,
        currency: str,
        email: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Initializes a payment transaction.
        :param amount: The amount to charge (in the smallest currency unit, e.g., kobo for NGN).
        :param currency: The currency code (e.g., 'NGN').
        :param email: The customer's email address.
        :param metadata: Optional metadata to attach to the transaction.
        :return: A dictionary containing the transaction reference and authorization URL.
        """
        return await paystack_gateway_impl.initialize_transaction(amount=amount, currency=currency, email=email, metadata=metadata, callback_url=callback_url)

    @abc.abstractmethod
    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verifies the status of a completed transaction.
        :param reference: The unique transaction reference.
        :return: A dictionary containing the full transaction details.
        """
        return await paystack_gateway_impl.verify_transaction(reference=reference)

    @abc.abstractmethod
    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Processes an incoming webhook event and verifies its signature.
        :param payload: The raw body of the webhook request.
        :param signature: The signature from the request header.
        :return: A dictionary containing the processed event data.
        :raises GatewaySignatureVerificationError: If the signature is invalid.
        """
        return await paystack_gateway_impl.handle_webhook(payload=payload, signature=signature)

    @abc.abstractmethod
    async def refund_transaction(self, reference: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """
        Initiates a refund for a transaction.
        :param reference: The transaction reference to refund.
        :param amount: The amount to refund (in the smallest currency unit). If None, full refund.
        :return: A dictionary containing the refund details.
        """
        return await paystack_gateway_impl.refund_transaction(reference=reference, amount=amount)

    @abc.abstractmethod
    async def close(self) -> None:
        """
        Closes the underlying HTTP client session.
        """
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _make_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Internal method to make an authenticated API request.
        """
        try:
            response = await self._client.request(
                method=method,
                url=path,
                json=json_data,
                params=params,
            )
            response.raise_for_status()
            
            data = response.json()
            if not data.get('status'):
                # Paystack specific check for 'status' field in response body
                raise GatewayAPIError(
                    message=data.get('message', 'API call failed with no specific message.'),
                    status_code=response.status_code,
                    response_data=data
                )
            
            return data.get('data', data)

        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                message = error_data.get('message', f"HTTP error {e.response.status_code}")
            except json.JSONDecodeError:
                message = f"HTTP error {e.response.status_code}: {e.response.text[:100]}..."
                error_data = None
            
            raise GatewayAPIError(
                message=message,
                status_code=e.response.status_code,
                response_data=error_data
            ) from e
        except httpx.RequestError as e:
            raise GatewayConnectionError(f"Network or connection error: {e}") from e

# --- Paystack Gateway Implementation ---

class PaystackGateway(BasePaymentGateway):
    """
    Concrete implementation for the Paystack payment gateway.
    
    Paystack is a Nigerian payment gateway that supports card payments, 
    bank transfers, and USSD. It operates in Nigeria, Ghana, South Africa, 
    and Kenya.
    """
    BASE_URL = "https://api.paystack.co"
    SUPPORTED_CURRENCIES = ["NGN", "GHS", "ZAR", "USD"] # Common African currencies + USD

    @retry_with_exponential_backoff()
    async def initialize_transaction(
        self,
        amount: int,
        currency: str,
        email: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Initializes a payment transaction using Paystack's /transaction/initialize endpoint.
        
        :param amount: The amount to charge (in the smallest currency unit, e.g., kobo for NGN).
        :param currency: The currency code (e.g., 'NGN').
        :param email: The customer's email address.
        :param metadata: Optional metadata to attach to the transaction.
        :return: A dictionary containing the transaction reference and authorization URL.
        :raises ValueError: If the currency is not supported.
        :raises GatewayAPIError: For API-specific errors.
        """
        if currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency {currency} is not supported by PaystackGateway.")

        payload = {
            "email": email,
            "amount": amount, # Paystack expects amount in kobo/smallest unit
            "currency": currency,
            "metadata": metadata or {},
            **kwargs
        }
        
        response_data = await self._make_request(
            method="POST",
            path="/transaction/initialize",
            json_data=payload
        )
        
        return {
            "reference": response_data.get("reference"),
            "authorization_url": response_data.get("authorization_url"),
            "raw_data": response_data
        }

    @retry_with_exponential_backoff()
    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verifies the status of a completed transaction using Paystack's /transaction/verify/:reference endpoint.
        
        :param reference: The unique transaction reference.
        :return: A dictionary containing the full transaction details.
        :raises GatewayVerificationError: If the transaction status is not 'success'.
        :raises GatewayAPIError: For API-specific errors.
        """
        response_data = await self._make_request(
            method="GET",
            path=f"/transaction/verify/{reference}"
        )
        
        # Paystack returns a 'status' field in the data object, which should be 'success'
        if response_data.get('status') != 'success':
            raise GatewayVerificationError(
                f"Transaction verification failed for reference {reference}. Status: {response_data.get('status')}"
            )

        return response_data

    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Processes an incoming webhook event and verifies its signature using HMAC SHA512.
        
        :param payload: The raw body of the webhook request.
        :param signature: The signature from the request header (x-paystack-signature).
        :return: A dictionary containing the processed event data.
        :raises GatewaySignatureVerificationError: If the signature is invalid.
        :raises GatewayWebhookError: For errors in processing the webhook payload.
        """
        # 1. Verify Signature
        # Paystack uses HMAC SHA512 to sign webhooks with the secret key
        expected_signature = hmac.new(
            key=self._secret_key.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise GatewaySignatureVerificationError("Webhook signature verification failed.")

        # 2. Parse Payload
        try:
            event_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise GatewayWebhookError(f"Invalid JSON payload: {e}") from e

        # 3. Return event data
        return event_data

    @retry_with_exponential_backoff()
    async def refund_transaction(self, reference: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """
        Initiates a refund for a transaction using Paystack's /refund endpoint.
        
        :param reference: The transaction reference to refund.
        :param amount: The amount to refund (in the smallest currency unit). If None, full refund.
        :return: A dictionary containing the refund details.
        :raises GatewayAPIError: For API-specific errors.
        """
        payload = {
            "transaction": reference,
        }
        if amount is not None:
            # Paystack expects amount in kobo/smallest unit
            payload["amount"] = amount 

        response_data = await self._make_request(
            method="POST",
            path="/refund",
            json_data=payload
        )
        
        return response_data

    async def close(self) -> None:
        """
        Closes the underlying HTTP client session.
        """
        await self._client.aclose()