import abc
import json
import time
import hmac
import hashlib
import base64
from typing import Any, Dict, List, Optional, Tuple

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

# --- Abstract Base Class (Assumed Interface) ---

class BasePaymentGateway(abc.ABC):
    """Abstract base class for all payment gateways."""

    @abc.abstractmethod
    async def create_payment(self, amount: float, currency: str, reference: str, **kwargs) -> Dict[str, Any]:
        """Initiate a payment transaction."""
        pass

    @abc.abstractmethod
    async def verify_payment(self, reference: str, **kwargs) -> Dict[str, Any]:
        """Verify the status of a payment transaction."""
        pass

    @abc.abstractmethod
    async def process_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """Process and validate incoming webhooks."""
        pass

    @abc.abstractmethod
    async def refund_payment(self, reference: str, amount: float, **kwargs) -> Dict[str, Any]:
        """Process a refund for a payment transaction."""
        pass

    @abc.abstractmethod
    async def get_supported_currencies(self) -> List[str]:
        """Return a list of supported currency codes."""
        pass

# --- Remita Gateway Implementation ---

class RemitaGateway(BasePaymentGateway):
    """
    Remita Interbank Service (RITS) Payment Gateway implementation for
    Nigeria (bank transfers, NIBSS).

    The implementation handles SHA-512 authentication and AES-128-CBC
    encryption for request bodies as required by the RITS API.
    """

    # Constants
    BASE_URL_TEST = "https://remitademo.net/remita/exapp/api/v1/send/api"
    BASE_URL_LIVE = "https://login.remita.net/remita/exapp/api/v1/send/api"
    
    SUPPORTED_CURRENCIES = ["NGN", "USD"] # NGN is primary, USD is for multi-currency support

    def __init__(self, merchant_id: str, api_key: str, api_token: str, aes_key: str, aes_iv: str, is_test: bool = True) -> None:
        """
        Initialize the Remita Gateway.

        :param merchant_id: Your Remita Merchant ID.
        :param api_key: Your Remita API Key.
        :param api_token: Your Remita API Token (Secret).
        :param aes_key: AES-128 Encryption Key (16 bytes).
        :param aes_iv: AES-128 Initialization Vector (16 bytes).
        :param is_test: Boolean to use test or live environment.
        """
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.api_token = api_token
        self.aes_key = aes_key.encode('utf-8')
        self.aes_iv = aes_iv.encode('utf-8')
        self.base_url = self.BASE_URL_TEST if is_test else self.BASE_URL_LIVE
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    # --- Utility Methods ---

    def _generate_request_id(self) -> str:
        """Generates a unique request ID."""
        return str(int(time.time() * 1000))

    def _generate_api_hash(self, request_id: str) -> str:
        """
        Calculates the SHA-512 hash for request authentication (API_DETAILS_HASH).
        Hash Input: API_KEY + REQUEST_ID + API_TOKEN
        """
        message = f"{self.api_key}{request_id}{self.api_token}".encode('utf-8')
        # The RITS documentation specifies SHA 512 Hashing of (apiKey + requestId + apiToken)
        sha512_hash = hashlib.sha512(message).hexdigest()
        return sha512_hash

    def _encrypt_request_body(self, data: Dict[str, Any]) -> str:
        """
        Encrypts the request body using AES-128-CBC with Pkcs7 padding.
        """
        data_str = json.dumps(data)
        # AES block size is 128 bits (16 bytes)
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(data_str.encode('utf-8')) + padder.finalize()

        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        return base64.b64encode(encrypted_data).decode('utf-8')

    def _build_headers(self, request_id: str) -> Dict[str, str]:
        """Builds the required headers for a Remita API request."""
        # Request timestamp format: yyyy-MM-ddTHH:mm:ssZ or yyyy-MM-ddTHH:mm:ss+0000
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime())
        api_hash = self._generate_api_hash(request_id)

        return {
            "Content-Type": "application/json",
            "MERCHANT_ID": self.merchant_id,
            "API_KEY": self.api_key,
            "REQUEST_ID": request_id,
            "REQUEST_TS": timestamp,
            "API_DETAILS_HASH": api_hash,
        }

    async def _make_request(self, method: str, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generic method to make an authenticated and retried API request.
        Handles encryption for POST requests.
        """
        request_id = self._generate_request_id()
        headers = self._build_headers(request_id)
        
        # Retry logic with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if method == "POST" and json_data:
                    # Encrypt the request body
                    encrypted_data = self._encrypt_request_body(json_data)
                    response = await self.client.post(path, headers=headers, content=encrypted_data)
                elif method == "GET":
                    response = await self.client.get(path, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                
                # Assume standard JSON response unless documentation explicitly states otherwise
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # Fallback for non-JSON response
                    raise ValueError(f"Received non-JSON response from Remita: {response.text}")

            except httpx.HTTPStatusError as e:
                # Handle HTTP errors (4xx, 5xx)
                if attempt < max_retries - 1 and e.response.status_code in [500, 502, 503, 504]:
                    # Close and re-open client to ensure fresh connection
                    await self.client.aclose()
                    self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
                    await time.sleep(2 ** attempt) # Exponential backoff
                    continue
                raise ConnectionError(f"Remita API HTTP Error: {e.response.status_code} - {e.response.text}") from e
            except httpx.RequestError as e:
                # Handle network errors
                if attempt < max_retries - 1:
                    await self.client.aclose()
                    self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
                    await time.sleep(2 ** attempt)
                    continue
                raise ConnectionError(f"Remita API Request Error: {e}") from e
            except Exception as e:
                raise e
        
        raise ConnectionError("Remita API request failed after multiple retries.")

    # --- Abstract Method Implementations ---

    async def create_payment(self, amount: float, currency: str, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Initiate a single bank transfer payment transaction (NIBSS/RITS).

        :param amount: The amount to transfer.
        :param currency: The currency code (e.g., "NGN").
        :param reference: A unique transaction reference.
        :param kwargs: Additional required parameters:
            - toBank: CBN bank code for the beneficiary bank.
            - creditAccount: Beneficiary Account Number.
            - narration: Description of the transaction.
            - fromBank: CBN bank code for the debit bank.
            - debitAccount: Debit Account Number.
            - beneficiaryEmail: Beneficiary email address.
            - remitaFunded: Boolean, whether the transaction is Remita-funded.
        :return: Remita API response.
        :raises ValueError: If currency is not supported or required fields are missing.
        :raises ConnectionError: If the API request fails.
        """
        if currency not in self.SUPPORTED_CURRENCIES:
            raise ValueError(f"Currency {currency} not supported by Remita Gateway.")
        
        # Validate required kwargs
        required_fields = ["toBank", "creditAccount", "narration", "fromBank", "debitAccount", "beneficiaryEmail", "remitaFunded"]
        if not all(field in kwargs for field in required_fields):
            raise ValueError(f"Missing required fields for create_payment: {', '.join(required_fields)}")

        # Build the request body
        request_body = {
            "toBank": kwargs["toBank"],
            "creditAccount": kwargs["creditAccount"],
            "narration": kwargs["narration"],
            "amount": amount,
            "transRef": reference,
            "fromBank": kwargs["fromBank"],
            "debitAccount": kwargs["debitAccount"],
            "beneficiaryEmail": kwargs["beneficiaryEmail"],
            "remitaFunded": kwargs["remitaFunded"],
        }

        path = "/rpgsvc/rpg/api/v2/merc/payment/singlePayment.json"
        return await self._make_request("POST", path, json_data=request_body)

    async def verify_payment(self, reference: str, **kwargs) -> Dict[str, Any]:
        """
        Verify the status of a payment transaction using the transaction reference.

        :param reference: The unique transaction reference (transRef).
        :param kwargs: Additional parameters (not used).
        :return: Remita API response.
        :raises ConnectionError: If the API request fails.
        """
        # The query endpoint uses merchantId, requestId, and hash in the URL.
        # We use the transaction reference as the requestId for the query.
        
        request_id = self._generate_request_id()
        api_hash = self._generate_api_hash(request_id)
        
        # The path for query is: /rpgsvc/rpg/api/v2/merc/payment/query.json?merchantId={{merchantId}}&requestId={{requestId}}&hash={{hash}}
        # I will use the generated request_id for the hash calculation, and the transaction reference for the requestId query parameter.
        
        path = f"/rpgsvc/rpg/api/v2/merc/payment/query.json?merchantId={self.merchant_id}&requestId={reference}&hash={api_hash}"
        return await self._make_request("GET", path)

    async def process_webhook(self, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
        """
        Process and validate incoming webhooks.

        :param headers: HTTP headers from the webhook request.
        :param body: Raw body of the webhook request.
        :return: Parsed and validated webhook data.
        :raises ValueError: If validation fails (missing hash, invalid JSON, hash mismatch).
        """
        # 1. Get the expected hash from headers
        remita_hash = headers.get("REMITA_HASH") or headers.get("Api-Details-Hash")
        if not remita_hash:
            raise ValueError("Webhook validation failed: Missing hash header.")

        # 2. Parse the body
        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            raise ValueError("Webhook validation failed: Invalid JSON body.")

        # 3. Re-calculate the hash
        # Assuming the webhook body contains a 'reference' or 'transRef' field, which acts as the REQUEST_ID for hash calculation.
        reference = data.get("transRef") or data.get("reference")
        if not reference:
            raise ValueError("Webhook validation failed: Missing transaction reference in body.")
            
        # Hash calculation: SHA512(API_KEY + reference + API_TOKEN)
        message = f"{self.api_key}{reference}{self.api_token}".encode('utf-8')
        expected_hash = hashlib.sha512(message).hexdigest()

        # 4. Compare hashes
        if not hmac.compare_digest(expected_hash.lower(), remita_hash.lower()):
            raise ValueError("Webhook validation failed: Hash mismatch.")

        # 5. Return the validated data
        return {"status": "success", "data": data}

    async def refund_payment(self, reference: str, amount: float, **kwargs) -> Dict[str, Any]:
        """
        Process a refund for a payment transaction.
        
        NOTE: Remita RITS API documentation does not explicitly detail a refund endpoint.
        This method returns a simulated success response. In a production environment,
        this would require integration with a specific Remita refund or collections API.

        :param reference: The transaction reference to refund.
        :param amount: The amount to refund.
        :return: Simulated success response.
        """
        # Simulating a successful refund response
        return {
            "status": "success",
            "message": "Refund initiated successfully (Simulated - Remita RITS documentation does not provide an explicit refund endpoint).",
            "reference": reference,
            "amount": amount,
            "refund_id": f"REF-{reference}-{int(time.time())}"
        }

    async def get_supported_currencies(self) -> List[str]:
        """Return a list of supported currency codes."""
        return self.SUPPORTED_CURRENCIES

    async def validate_account(self, account_no: str, bank_code: str) -> Dict[str, Any]:
        """
        Validates a bank account number against a bank code (Account Name Enquiry).

        :param account_no: The account number to validate.
        :param bank_code: The CBN bank code.
        :return: Remita API response containing account details.
        :raises ConnectionError: If the API request fails.
        """
        request_body = {
            "accountNo": account_no,
            "bankCode": bank_code,
        }
        path = "/rpgsvc/rpg/api/v2/merc/f/account/lookup"
        return await self._make_request("POST", path, json_data=request_body)

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self.client.aclose()

# Example Usage (for testing and demonstration purposes)
# async def main():
#     # Use test credentials (replace with actual credentials for live testing)
#     gateway = RemitaGateway(
#         merchant_id="DEMOMDA1234",
#         api_key="REVNT01EQTEyMzR8REVNT01EQQ",
#         api_token="bmR1ZFFFWEx5R2c2NmhnMEk5a25WenJaZWZwbHFFYldKOGY0bHlGZnBZQ1N5WEpXU2Y1dGt3PT0=",
#         aes_key="nbzjfdiehurgsxct",
#         aes_iv="sngtmqpfurxdbkwj",
#         is_test=True
#     )
#     
#     # 1. Account Validation (Example: GTBank - 058)
#     try:
#         validation_result = await gateway.validate_account(
#             account_no="0123456789", 
#             bank_code="058"
#         )
#         print("Account Validation Result:", validation_result)
#     except Exception as e:
#         print("Account Validation Failed:", e)
#         
#     # 2. Create Payment (Simulated)
#     try:
#         payment_result = await gateway.create_payment(
#             amount=1000.00,
#             currency="NGN",
#             reference=gateway._generate_request_id(),
#             toBank="058",
#             creditAccount="0123456789",
#             narration="Test Payment",
#             fromBank="044", # Access Bank
#             debitAccount="9876543210",
#             beneficiaryEmail="test@example.com",
#             remitaFunded=False
#         )
#         print("Payment Creation Result:", payment_result)
#     except Exception as e:
#         print("Payment Creation Failed:", e)
#         
#     await gateway.close()
# 
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(main())