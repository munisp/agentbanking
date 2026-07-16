import hmac
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Awaitable, TypeVar
from functools import wraps

import httpx
import asyncio

# --- Type Variables ---
T = TypeVar('T')

# --- Exceptions ---
class PaymentGatewayError(Exception):
    """Base exception for all payment gateway errors."""
    pass

class GatewayAPIError(PaymentGatewayError):
    """Raised for errors returned by the gateway's API."""
    def __init__(self, message: str, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code

class GatewayAuthenticationError(PaymentGatewayError):
    """Raised for authentication failures."""
    pass

class GatewayWebhookError(PaymentGatewayError):
    """Raised for webhook processing errors (e.g., signature mismatch)."""
    pass

# --- Utility Functions and Decorators ---

def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (httpx.ConnectError, httpx.Timeout)
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    A decorator to implement exponential backoff and retry logic for async functions.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    print(f"Attempt {attempt + 1} failed with {type(e).__name__}. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

# --- Base Class Definition ---

class BasePaymentGateway(ABC):
    """
    Abstract Base Class for all payment gateway integrations.
    Defines the required interface for a production-ready gateway.
    """
    
    @abstractmethod
    async def create_payment(
        self, 
        amount: float, 
        currency: str, 
        order_id: str, 
        customer_info: Dict[str, Any], 
        payment_method: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Initiates a payment transaction.
        
        :param amount: The amount to charge.
        :param currency: The currency code (e.g., 'NGN').
        :param order_id: A unique identifier for the order.
        :param customer_info: Dictionary containing customer details.
        :param payment_method: The desired payment method (e.g., 'WALLET', 'USSD', 'BANK_TRANSFER').
        :return: A dictionary containing the gateway's response, typically a redirect URL or transaction reference.
        """
        pass

    @abstractmethod
    async def verify_payment(self, transaction_ref: str) -> Dict[str, Any]:
        """
        Verifies the status of a payment transaction.
        
        :param transaction_ref: The gateway's unique transaction reference.
        :return: A dictionary containing the transaction status and details.
        """
        pass

    @abstractmethod
    async def handle_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming webhook notification from the gateway.
        
        :param headers: The HTTP headers of the webhook request.
        :param payload: The JSON body of the webhook request.
        :return: A dictionary containing the processed webhook data.
        :raises GatewayWebhookError: If signature verification fails.
        """
        pass

    @abstractmethod
    async def refund_payment(self, transaction_ref: str, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Initiates a refund for a completed transaction.
        
        :param transaction_ref: The transaction to refund.
        :param amount: The amount to refund (full refund if None).
        :return: A dictionary containing the refund status and details.
        """
        pass

# --- Opay Gateway Implementation ---

class OpayGateway(BasePaymentGateway):
    """
    Opay (Nigeria) Payment Gateway Integration.
    Supports Wallet, USSD, and Bank Transfer payments.
    """
    
    BASE_URL = "https://cashierapi.opayweb.com" # Production URL, adjust for sandbox
    SANDBOX_URL = "https://cashierapi.test4.opayweb.com"
    
    SUPPORTED_CURRENCIES = ["NGN"]
    
    def __init__(
        self, 
        merchant_id: str, 
        public_key: str, 
        secret_key: str, 
        is_sandbox: bool = False
    ) -> None:
        """
        Initializes the Opay Gateway client.
        
        :param merchant_id: Your Opay Merchant ID.
        :param public_key: Your Opay Public Key (used in headers).
        :param secret_key: Your Opay Secret Key (used for HMAC signature).
        :param is_sandbox: Flag to use the sandbox environment.
        """
        self.merchant_id = merchant_id
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = self.SANDBOX_URL if is_sandbox else self.BASE_URL
        self.http_client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    def _generate_signature(self, payload: Dict[str, Any]) -> str:
        """
        Generates the HMAC-SHA512 signature for the request payload.
        
        The signature is calculated over the JSON string representation of the payload,
        signed with the merchant's secret key.
        """
        # 1. Convert payload to JSON string (ensure no extra spaces/newlines)
        # Opay documentation suggests sorting keys and compact representation, 
        # but a simple json.dumps is often sufficient if the gateway expects it.
        # For robustness, we'll use a canonical JSON representation.
        canonical_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        
        # 2. Encode the JSON string and the secret key
        message = canonical_json.encode('utf-8')
        key = self.secret_key.encode('utf-8')
        
        # 3. Calculate HMAC-SHA512
        signature = hmac.new(key, message, hashlib.sha512).hexdigest()
        
        return signature

    def _build_headers(self, signature: str) -> Dict[str, str]:
        """
        Builds the required HTTP headers for Opay API requests.
        """
        return {
            "MerchantId": self.merchant_id,
            "PublicKey": self.public_key,
            "Content-Type": "application/json",
            "Signature": signature,
            "RequestId": str(int(time.time() * 1000)), # Unique request ID
        }

    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal method to handle API request, signature, and error parsing.
        """
        signature = self._generate_signature(payload)
        headers = self._build_headers(signature)
        
        @retry_with_exponential_backoff()
        async def execute_request() -> None:
            response = await self.http_client.post(endpoint, headers=headers, json=payload)
            
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                raise GatewayAPIError(
                    f"Invalid JSON response from Opay: {response.text}", 
                    "JSON_ERROR", 
                    response.status_code
                )

            if response.status_code != 200 or response_data.get("code") != "000000":
                # Handle specific Opay error codes
                error_code = response_data.get("code", "UNKNOWN_ERROR")
                error_msg = response_data.get("message", "An unknown error occurred.")
                
                if error_code in ["000001", "000002"]: # Example: Authentication/Signature errors
                    raise GatewayAuthenticationError(f"Opay Authentication Error: {error_msg}")
                
                raise GatewayAPIError(
                    f"Opay API Error ({error_code}): {error_msg}", 
                    error_code, 
                    response.status_code
                )
            
            return response_data

        return await execute_request()

    async def create_payment(
        self, 
        amount: float, 
        currency: str, 
        order_id: str, 
        customer_info: Dict[str, Any], 
        payment_method: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Initiates a payment transaction via Opay.
        
        The actual endpoint used depends on the desired payment method (e.g., 
        'cashier/v1/cashier/initialize' for general payments).
        This implementation uses the general cashier initialize endpoint which 
        can handle various methods like wallet, USSD, and bank transfer via redirect.
        
        :param amount: The amount to charge (in the smallest unit, e.g., kobo for NGN).
        :param currency: The currency code (must be 'NGN').
        :param order_id: A unique identifier for the order.
        :param customer_info: Dictionary containing customer details (e.g., 'email', 'name').
        :param payment_method: The desired payment method (ignored for general cashier, 
                               but kept for interface compatibility).
        :param kwargs: Additional parameters like 'callbackUrl', 'returnUrl'.
        :return: A dictionary containing the gateway's response, including 'cashierUrl' for redirect.
        """
        if currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency {currency} not supported by Opay Gateway.")
            
        # Opay expects amount in the smallest unit (e.g., kobo for NGN)
        amount_kobo = int(amount * 100)
        
        payload = {
            "reference": order_id,
            "amount": amount_kobo,
            "currency": currency,
            "productName": kwargs.get("product_name", "Payment for Order"),
            "payMethod": "BankCard", # Use a general method or specific one if required
            "callbackUrl": kwargs.get("callback_url"),
            "returnUrl": kwargs.get("return_url"),
            "expireAt": kwargs.get("expire_at", 30), # Expiration in minutes
            "userInfo": {
                "userEmail": customer_info.get("email"),
                "userId": customer_info.get("id", order_id),
                "userPhone": customer_info.get("phone"),
            }
        }
        
        # Opay's general payment endpoint
        endpoint = "/api/v3/cashier/initialize"
        
        return await self._make_request(endpoint, payload)

    async def verify_payment(self, transaction_ref: str) -> Dict[str, Any]:
        """
        Verifies the status of a payment transaction using the order reference.
        
        :param transaction_ref: The merchant's unique order reference (the 'reference' used in create_payment).
        :return: A dictionary containing the transaction status and details.
        """
        payload = {
            "reference": transaction_ref
        }
        
        endpoint = "/api/v3/cashier/status"
        
        return await self._make_request(endpoint, payload)

    async def refund_payment(self, transaction_ref: str, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Initiates a refund for a completed transaction.
        
        :param transaction_ref: The transaction to refund (Opay's transaction ID or merchant reference).
        :param amount: The amount to refund (in the base unit, e.g., Naira).
        :return: A dictionary containing the refund status and details.
        """
        if amount is None:
            # In a real scenario, we'd first verify the transaction to get the original amount
            # For this mock, we'll assume the full amount is passed or a default is used.
            raise NotImplementedError("Full refund without amount is not fully implemented. Please specify amount.")
            
        amount_kobo = int(amount * 100)
        
        payload = {
            "reference": f"REFUND_{transaction_ref}_{int(time.time())}", # Unique refund reference
            "orderNo": transaction_ref, # Assuming transaction_ref is the Opay orderNo
            "amount": amount_kobo,
            "reason": "Customer request"
        }
        
        endpoint = "/api/v3/transaction/refund"
        
        return await self._make_request(endpoint, payload)

    def _verify_webhook_signature(self, headers: Dict[str, str], payload_str: str) -> bool:
        """
        Verifies the webhook signature against the calculated HMAC-SHA512 hash.
        
        Opay webhooks typically include a 'Signature' header. The payload is the raw JSON body.
        """
        expected_signature = headers.get("Signature")
        if not expected_signature:
            return False
            
        # 1. Encode the raw payload string and the secret key
        message = payload_str.encode('utf-8')
        key = self.secret_key.encode('utf-8')
        
        # 2. Calculate HMAC-SHA512
        calculated_signature = hmac.new(key, message, hashlib.sha512).hexdigest()
        
        # 3. Compare signatures (case-insensitive comparison is safer)
        return hmac.compare_digest(calculated_signature.lower(), expected_signature.lower())

    async def handle_webhook(self, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming webhook notification from Opay.
        
        :param headers: The HTTP headers of the webhook request.
        :param payload: The JSON body of the webhook request.
        :return: A dictionary containing the processed webhook data.
        :raises GatewayWebhookError: If signature verification fails.
        """
        # The raw payload string is needed for signature verification.
        # We use the same canonical serialization as in _generate_signature.
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        
        if not self._verify_webhook_signature(headers, payload_str):
            raise GatewayWebhookError("Webhook signature verification failed.")
            
        # Webhook is verified, now process the event
        event_type = payload.get("eventType")
        
        # Example processing logic
        if event_type == "PAYMENT_SUCCESS":
            # In a real application, this is where you would update your database
            print(f"Payment successful for reference: {payload.get('reference')}")
        elif event_type == "PAYMENT_FAILURE":
            print(f"Payment failed for reference: {payload.get('reference')}")
        
        return {
            "status": "success",
            "event_type": event_type,
            "data": payload
        }

# --- Production implementation imported ---
from .gtpay_gateway_full import OpayGateway as OpayGatewayProduction  # noqa: F401
