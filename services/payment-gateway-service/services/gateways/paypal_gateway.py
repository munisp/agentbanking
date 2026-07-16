import abc
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Type

import httpx
import asyncio
from httpx import AsyncClient, Response

# --- Custom Exceptions ---

class PaymentGatewayError(Exception):
    """Base exception for all payment gateway errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details

class AuthenticationError(PaymentGatewayError):
    """Raised when authentication with the gateway fails."""
    pass

class WebhookVerificationError(PaymentGatewayError):
    """Raised when a webhook signature verification fails."""
    pass

class PaymentProcessingError(PaymentGatewayError):
    """Raised for errors during payment creation or capture."""
    pass

class RefundProcessingError(PaymentGatewayError):
    """Raised for errors during refund processing."""
    pass

# --- Base Gateway Interface ---

class BasePaymentGateway(abc.ABC):
    """
    Abstract base class for all payment gateway integrations.
    Defines the core methods that every gateway must implement.
    """

    @abc.abstractmethod
    def __init__(self, client_id: str, client_secret: str, webhook_id: str, sandbox: bool = False) -> None:
        """Initialize the gateway with credentials and configuration."""
        pass

    @abc.abstractmethod
    async def _get_access_token(self) -> str:
        """
        Retrieves a new OAuth 2.0 access token from the gateway.
        Must handle token caching and expiration.
        """
        pass

    @abc.abstractmethod
    async def create_payment(self, amount: float, currency: str, description: str, **kwargs) -> Dict[str, Any]:
        """
        Initiates a payment transaction.
        Returns a dictionary containing the payment ID and a redirect URL for the user.
        """
        pass

    @abc.abstractmethod
    async def capture_payment(self, payment_id: str, **kwargs) -> Dict[str, Any]:
        """
        Captures an authorized payment.
        Returns a dictionary with the transaction details.
        """
        pass

    @abc.abstractmethod
    async def refund_payment(self, transaction_id: str, amount: float, currency: str, **kwargs) -> Dict[str, Any]:
        """
        Processes a refund for a captured transaction.
        Returns a dictionary with the refund details.
        """
        pass

    @abc.abstractmethod
    async def verify_webhook_signature(self, headers: Dict[str, str], body: str) -> Dict[str, Any]:
        """
        Verifies the signature of an incoming webhook payload.
        Raises WebhookVerificationError on failure.
        Returns the verified webhook event data.
        """
        pass

    @abc.abstractmethod
    async def _api_call(self, method: str, endpoint: str, json_data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Internal method to handle all API calls, including authentication,
        retry logic, and error handling.
        """
        pass

# --- PayPal Gateway Implementation ---

class PayPalGateway(BasePaymentGateway):
    """
    Production-ready implementation for the PayPal (International - wallet, cards)
    payment gateway using the PayPal REST API (v2).
    """

    # PayPal supports 25 currencies. We'll list a few common ones and include
    # the African currencies that are generally supported (e.g., USD, EUR, GBP
    # which are used for international transactions in many African countries,
    # and specific ones like ZAR if supported).
    # Based on research, PayPal supports 25 currencies, including USD, EUR, GBP,
    # and ZAR (South African Rand) is a notable one for Africa.
    SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "ZAR", "CAD", "AUD", "JPY"]
    
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 1.0  # seconds

    def __init__(self, client_id: str, client_secret: str, webhook_id: str, sandbox: bool = False) -> None:
        """
        Initialize the PayPal Gateway.

        :param client_id: Your PayPal application's Client ID.
        :param client_secret: Your PayPal application's Client Secret.
        :param webhook_id: The ID of the webhook endpoint registered with PayPal.
        :param sandbox: If True, use the sandbox environment. Defaults to False.
        """
        if not all([client_id, client_secret, webhook_id]):
            raise ValueError("Client ID, Client Secret, and Webhook ID must be provided.")

        self.client_id = client_id
        self.client_secret = client_secret
        self.webhook_id = webhook_id
        self.base_url = "https://api-m.sandbox.paypal.com" if sandbox else "https://api-m.paypal.com"
        
        # httpx client for async requests
        self.client: AsyncClient = AsyncClient(base_url=self.base_url, timeout=30.0)
        
        # Token management
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        """
        Retrieves a new OAuth 2.0 access token from PayPal.
        Handles token caching and expiration.

        :raises AuthenticationError: If token retrieval fails.
        :return: The valid access token string.
        """
        if self._access_token and self._token_expires_at > time.time() + 60:
            return self._access_token

        auth_url = "/v1/oauth2/token"
        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        auth_data = {
            "grant_type": "client_credentials"
        }

        try:
            # Use basic auth for token endpoint
            response = await self.client.post(
                auth_url,
                headers=auth_headers,
                data=auth_data,
                auth=(self.client_id, self.client_secret)
            )
            response.raise_for_status()
            data = response.json()
            
            self._access_token = data["access_token"]
            # PayPal token expiration is typically 28800 seconds (8 hours).
            # We subtract a buffer (e.g., 600s) to refresh proactively.
            expires_in = data.get("expires_in", 28800)
            self._token_expires_at = time.time() + expires_in - 600
            
            return self._access_token

        except httpx.HTTPStatusError as e:
            raise AuthenticationError(
                f"Failed to get PayPal access token. Status: {e.response.status_code}",
                status_code=e.response.status_code,
                details=e.response.json()
            ) from e
        except Exception as e:
            raise AuthenticationError(f"An unexpected error occurred during token retrieval: {e}") from e

    async def _api_call(self, method: str, endpoint: str, json_data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Internal method to handle all PayPal API calls with authentication,
        retry logic (exponential backoff), and centralized error handling.

        :param method: HTTP method (e.g., 'GET', 'POST', 'PATCH').
        :param endpoint: The API endpoint path (e.g., '/v2/checkout/orders').
        :param json_data: JSON payload for the request body.
        :param headers: Additional headers to include.
        :raises PaymentGatewayError: For any API call failure after retries.
        :return: The JSON response from the API.
        """
        token = await self._get_access_token()
        
        default_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)

        for attempt in range(self.MAX_RETRIES):
            try:
                response: Response = await self.client.request(
                    method,
                    endpoint,
                    json=json_data,
                    headers=default_headers
                )
                
                # Check for rate limiting (429) or server errors (5xx) to retry
                if response.status_code in [429, 500, 502, 503, 504]:
                    if attempt < self.MAX_RETRIES - 1:
                        delay = self.RETRY_DELAY_BASE * (2 ** attempt) + (time.time() % 1)
                        await asyncio.sleep(delay)
                        continue
                
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                # Handle non-retryable errors (4xx)
                status_code = e.response.status_code
                try:
                    details = e.response.json()
                except json.JSONDecodeError:
                    details = {"message": e.response.text}
                
                error_message = f"PayPal API call failed ({method} {endpoint}). Status: {status_code}"
                
                if status_code == 401:
                    raise AuthenticationError(error_message, status_code, details) from e
                elif status_code in [400, 404, 422]:
                    # Use a more specific error based on the operation
                    if "orders" in endpoint or "payments" in endpoint:
                        raise PaymentProcessingError(error_message, status_code, details) from e
                    elif "refunds" in endpoint:
                        raise RefundProcessingError(error_message, status_code, details) from e
                    else:
                        raise PaymentGatewayError(error_message, status_code, details) from e
                else:
                    # Catch all other non-retryable errors
                    raise PaymentGatewayError(error_message, status_code, details) from e
            
            except httpx.RequestError as e:
                # Handle network-related errors
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt) + (time.time() % 1)
                    await asyncio.sleep(delay)
                    continue
                raise PaymentGatewayError(f"Network error during PayPal API call: {e}") from e
            
            except Exception as e:
                raise PaymentGatewayError(f"An unexpected error occurred during API call: {e}") from e

        # Should be unreachable if retry logic is correct, but for safety:
        raise PaymentGatewayError(f"PayPal API call failed after {self.MAX_RETRIES} attempts.")

    async def create_payment(self, amount: float, currency: str, description: str, **kwargs) -> Dict[str, Any]:
        """
        Creates a PayPal Order (v2/checkout/orders) for a payment.
        This is the first step for a PayPal checkout flow (wallet or cards).

        :param amount: The total amount to charge.
        :param currency: The three-letter ISO-4217 currency code.
        :param description: A brief description of the purchase.
        :param kwargs: Additional parameters, e.g., 'return_url', 'cancel_url'.
        :raises PaymentProcessingError: If the order creation fails.
        :return: A dictionary containing the PayPal Order ID and approval link.
        """
        if currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency {currency} is not supported by this gateway.")

        return_url = kwargs.get("return_url", "https://example.com/success")
        cancel_url = kwargs.get("cancel_url", "https://example.com/cancel")

        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "description": description,
                    "amount": {
                        "currency_code": currency,
                        "value": f"{amount:.2f}"
                    }
                }
            ],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING"
            }
        }

        try:
            response = await self._api_call(
                method="POST",
                endpoint="/v2/checkout/orders",
                json_data=order_data
            )
            
            order_id = response["id"]
            approval_link = next(
                (link["href"] for link in response["links"] if link["rel"] == "approve"),
                None
            )

            if not approval_link:
                raise PaymentProcessingError("PayPal order created but no approval link found.")

            return {
                "order_id": order_id,
                "approval_link": approval_link,
                "status": response["status"],
                "raw_response": response
            }

        except PaymentGatewayError as e:
            raise PaymentProcessingError(f"Failed to create PayPal order: {e}") from e

    async def capture_payment(self, payment_id: str, **kwargs) -> Dict[str, Any]:
        """
        Captures the funds for an authorized PayPal Order.
        This is typically called after the user approves the payment via the approval_link.

        :param payment_id: The PayPal Order ID (from create_payment).
        :param kwargs: Additional parameters (currently unused).
        :raises PaymentProcessingError: If the capture fails.
        :return: A dictionary with the capture transaction details.
        """
        endpoint = f"/v2/checkout/orders/{payment_id}/capture"
        
        try:
            response = await self._api_call(
                method="POST",
                endpoint=endpoint,
                json_data={} # Empty body is required for capture
            )

            # Extract the primary capture ID and status
            capture_details = response["purchase_units"][0]["payments"]["captures"][0]
            
            return {
                "transaction_id": capture_details["id"],
                "status": response["status"],
                "amount": capture_details["amount"]["value"],
                "currency": capture_details["amount"]["currency_code"],
                "raw_response": response
            }

        except PaymentGatewayError as e:
            raise PaymentProcessingError(f"Failed to capture PayPal order {payment_id}: {e}") from e

    async def refund_payment(self, transaction_id: str, amount: float, currency: str, **kwargs) -> Dict[str, Any]:
        """
        Processes a refund for a captured transaction.

        :param transaction_id: The PayPal Capture ID (from capture_payment).
        :param amount: The amount to refund.
        :param currency: The currency of the refund.
        :param kwargs: Additional parameters, e.g., 'reason'.
        :raises RefundProcessingError: If the refund fails.
        :return: A dictionary with the refund details.
        """
        endpoint = f"/v2/payments/captures/{transaction_id}/refund"
        
        refund_data = {
            "amount": {
                "currency_code": currency,
                "value": f"{amount:.2f}"
            },
            "note_to_payer": kwargs.get("reason", "Requested by customer.")
        }

        try:
            response = await self._api_call(
                method="POST",
                endpoint=endpoint,
                json_data=refund_data
            )

            return {
                "refund_id": response["id"],
                "status": response["status"],
                "amount": response["amount"]["value"],
                "currency": response["amount"]["currency_code"],
                "raw_response": response
            }

        except PaymentGatewayError as e:
            raise RefundProcessingError(f"Failed to process refund for transaction {transaction_id}: {e}") from e

    async def verify_webhook_signature(self, headers: Dict[str, str], body: str) -> Dict[str, Any]:
        """
        Verifies the signature of an incoming PayPal webhook payload using the
        PayPal Webhooks API (v1/notifications/verify-webhook-signature).

        :param headers: The HTTP headers from the incoming webhook request.
        :param body: The raw JSON body of the incoming webhook request.
        :raises WebhookVerificationError: If the verification fails.
        :return: The verified webhook event data (parsed JSON body).
        """
        verification_endpoint = "/v1/notifications/verify-webhook-signature"
        
        # Extract required headers
        try:
            auth_algo = headers["PAYPAL-AUTH-ALGO"]
            cert_url = headers["PAYPAL-CERT-URL"]
            transmission_id = headers["PAYPAL-TRANSMISSION-ID"]
            transmission_sig = headers["PAYPAL-TRANSMISSION-SIG"]
            transmission_time = headers["PAYPAL-TRANSMISSION-TIME"]
        except KeyError as e:
            raise WebhookVerificationError(f"Missing required PayPal webhook header: {e}")

        verification_data = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": self.webhook_id,
            "webhook_event": json.loads(body)
        }

        try:
            # Note: _api_call handles authentication and retries
            response = await self._api_call(
                method="POST",
                endpoint=verification_endpoint,
                json_data=verification_data
            )

            if response.get("verification_status") == "SUCCESS":
                return verification_data["webhook_event"]
            else:
                raise WebhookVerificationError(
                    f"PayPal webhook verification failed. Status: {response.get('verification_status')}",
                    details=response
                )

        except PaymentGatewayError as e:
            # Catch API errors and re-raise as a verification error
            raise WebhookVerificationError(f"API call to verify webhook failed: {e}") from e
        except json.JSONDecodeError as e:
            raise WebhookVerificationError(f"Failed to decode webhook body as JSON: {e}") from e