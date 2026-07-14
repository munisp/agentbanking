"""
BRICS Pay Payment Gateway Client - Refactored with NIBSS Architecture Pattern
Supports cross-border payments between BRICS nations (Brazil, Russia, India, China, South Africa)
"""

import httpx
import hashlib
import hmac
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class BRICSCurrency(str, Enum):
    """BRICS supported currencies"""
    BRL = "BRL"  # Brazilian Real
    RUB = "RUB"  # Russian Ruble
    INR = "INR"  # Indian Rupee
    CNY = "CNY"  # Chinese Yuan
    ZAR = "ZAR"  # South African Rand

class BRICSTransactionStatus(Enum):
    """BRICS Pay transaction status codes"""
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    PROCESSING = "processing"
    CANCELLED = "cancelled"

class BRICSPayError(Exception):
    """Base exception for BRICS Pay errors"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"BRICS Pay Error {code}: {message}")

class BRICSPayClient:
    """
    BRICS Pay Gateway Client
    Facilitates payments across BRICS nations using local currencies
    Refactored with NIBSS architecture pattern for production readiness
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        merchant_id: str,
        base_url: str = "https://api.brics-pay.com",
        timeout: int = 30
    ):
        """
        Initialize BRICS Pay client
        
        Args:
            api_key: BRICS Pay API key
            secret_key: Secret key for signing requests
            merchant_id: Merchant identifier
            base_url: BRICS Pay API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.merchant_id = merchant_id
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
        
        logger.info(f"BRICS Pay client initialized for merchant: {merchant_id}")
    
    def _generate_signature(self, payload: Dict) -> str:
        """
        Generate HMAC-SHA256 signature for request
        
        Args:
            payload: Request payload
            
        Returns:
            Hex-encoded signature
        """
        # Sort keys and create canonical string
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Generate HMAC-SHA256
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            canonical.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_headers(self, signature: str = None) -> Dict[str, str]:
        """Get request headers with authentication"""
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "X-Merchant-ID": self.merchant_id,
            "X-Request-Time": datetime.utcnow().isoformat()
        }
        if signature:
            headers["X-Signature"] = signature
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated request to BRICS Pay API
        Centralized error handling following NIBSS pattern
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            payload: Request payload for POST requests
            params: Query parameters for GET requests
            
        Returns:
            Response data
            
        Raises:
            BRICSPayError: On API errors
        """
        url = f"{self.base_url}{endpoint}"
        
        # Generate signature for POST requests
        if payload:
            signature = self._generate_signature(payload)
        else:
            signature = None
        
        headers = self._get_headers(signature)
        
        try:
            logger.info(f"BRICS Pay API request: {method} {endpoint}")
            
            if method.upper() == "POST":
                response = await self.client.post(url, json=payload, headers=headers)
            elif method.upper() == "GET":
                response = await self.client.get(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Log response
            logger.info(f"BRICS Pay API response: {response.status_code}")
            
            # Parse response
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise BRICSPayError(
                    code="INVALID_RESPONSE",
                    message="Invalid JSON response from BRICS Pay",
                    details={"status_code": response.status_code, "body": response.text}
                )
            
            # Check HTTP status
            if response.status_code != 200:
                raise BRICSPayError(
                    code=data.get("errorCode", str(response.status_code)),
                    message=data.get("message", "Request failed"),
                    details=data
                )
            
            # Check response status
            if data.get("status") != BRICSTransactionStatus.SUCCESS.value:
                raise BRICSPayError(
                    code=data.get("errorCode", "UNKNOWN"),
                    message=data.get("message", "Transaction failed"),
                    details=data
                )
            
            return data
            
        except httpx.TimeoutException:
            logger.error(f"BRICS Pay API timeout: {endpoint}")
            raise BRICSPayError(
                code="TIMEOUT",
                message="Request to BRICS Pay timed out",
                details={"endpoint": endpoint, "timeout": self.timeout}
            )
        except httpx.NetworkError as e:
            logger.error(f"BRICS Pay API network error: {str(e)}")
            raise BRICSPayError(
                code="NETWORK_ERROR",
                message="Network error connecting to BRICS Pay",
                details={"error": str(e)}
            )
        except BRICSPayError:
            raise
        except Exception as e:
            logger.error(f"BRICS Pay API unexpected error: {str(e)}")
            raise BRICSPayError(
                code="UNKNOWN_ERROR",
                message="Unexpected error",
                details={"error": str(e)}
            )
    
    async def initiate_transfer(
        self,
        source_currency: str,
        destination_currency: str,
        amount: float,
        source_account: str,
        destination_account: str,
        beneficiary_name: str,
        beneficiary_country: str,
        reference: str,
        purpose: str
    ) -> Dict:
        """
        Initiate cross-border BRICS transfer
        
        Args:
            source_currency: Source currency code
            destination_currency: Destination currency code
            amount: Transfer amount
            source_account: Source account number
            destination_account: Destination account number
            beneficiary_name: Beneficiary name
            beneficiary_country: Beneficiary country code
            reference: Unique transaction reference
            purpose: Transfer purpose
            
        Returns:
            Transfer response data
            
        Raises:
            BRICSPayError: On transfer failure
        """
        payload = {
            "merchantId": self.merchant_id,
            "sourceCurrency": source_currency,
            "destinationCurrency": destination_currency,
            "amount": amount,
            "sourceAccount": source_account,
            "destinationAccount": destination_account,
            "beneficiaryName": beneficiary_name,
            "beneficiaryCountry": beneficiary_country,
            "reference": reference,
            "purpose": purpose,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Initiating BRICS Pay transfer: {reference} - {amount} {source_currency}")
        
        response = await self._make_request("POST", "/v1/transfers", payload)
        
        logger.info(f"BRICS Pay transfer initiated: {response['data']['transferId']}")
        
        return {
            "transfer_id": response["data"]["transferId"],
            "status": response["data"]["status"],
            "reference": response["data"]["reference"],
            "source_amount": amount,
            "source_currency": source_currency,
            "destination_amount": response["data"]["destinationAmount"],
            "destination_currency": destination_currency,
            "exchange_rate": response["data"]["exchangeRate"],
            "fee": response["data"].get("fee", 0),
            "estimated_delivery": response["data"].get("estimatedDelivery"),
            "raw_response": response
        }
    
    async def get_transfer_status(self, transfer_id: str) -> Dict:
        """
        Query transfer status
        
        Args:
            transfer_id: BRICS Pay transfer ID
            
        Returns:
            Transfer status data
        """
        logger.info(f"Querying BRICS Pay transfer status: {transfer_id}")
        
        response = await self._make_request("GET", f"/v1/transfers/{transfer_id}")
        
        return {
            "transfer_id": transfer_id,
            "status": response["data"]["status"],
            "reference": response["data"].get("reference"),
            "source_amount": response["data"].get("sourceAmount"),
            "destination_amount": response["data"].get("destinationAmount"),
            "current_stage": response["data"].get("currentStage"),
            "updated_at": response["data"].get("updatedAt"),
            "raw_response": response
        }
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        amount: float = None
    ) -> Dict:
        """
        Get real-time exchange rate between BRICS currencies
        
        Args:
            from_currency: Source currency code
            to_currency: Destination currency code
            amount: Optional amount for conversion calculation
            
        Returns:
            Exchange rate data
        """
        params = {
            "from": from_currency,
            "to": to_currency
        }
        if amount:
            params["amount"] = amount
        
        logger.info(f"Fetching BRICS Pay exchange rate: {from_currency}/{to_currency}")
        
        response = await self._make_request("GET", "/v1/rates", params=params)
        
        return {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": response["data"]["rate"],
            "inverse_rate": response["data"].get("inverseRate"),
            "timestamp": response["data"]["timestamp"]
        }
    
    async def verify_account(
        self,
        account_number: str,
        country_code: str,
        currency: str
    ) -> Dict:
        """
        Verify beneficiary account in BRICS country
        
        Args:
            account_number: Account number to verify
            country_code: Country code
            currency: Currency code
            
        Returns:
            Account verification data
        """
        payload = {
            "accountNumber": account_number,
            "countryCode": country_code,
            "currency": currency
        }
        
        logger.info(f"Verifying BRICS Pay account: {account_number} in {country_code}")
        
        response = await self._make_request("POST", "/v1/accounts/verify", payload)
        
        return {
            "account_number": account_number,
            "account_name": response["data"]["accountName"],
            "bank_name": response["data"]["bankName"],
            "country_code": country_code,
            "is_valid": response["data"]["isValid"]
        }
    
    async def get_supported_corridors(self) -> List[Dict]:
        """
        Get list of supported payment corridors
        
        Returns:
            List of supported corridors
        """
        logger.info("Fetching BRICS Pay supported corridors")
        
        response = await self._make_request("GET", "/v1/corridors")
        
        return response["data"]["corridors"]
    
    async def get_transaction_limits(
        self,
        source_currency: str,
        destination_currency: str
    ) -> Dict:
        """
        Get transaction limits for currency pair
        
        Args:
            source_currency: Source currency code
            destination_currency: Destination currency code
            
        Returns:
            Transaction limits data
        """
        params = {
            "sourceCurrency": source_currency,
            "destinationCurrency": destination_currency
        }
        
        logger.info(f"Fetching BRICS Pay limits: {source_currency}/{destination_currency}")
        
        response = await self._make_request("GET", "/v1/limits", params=params)
        
        return {
            "source_currency": source_currency,
            "destination_currency": destination_currency,
            "min_amount": response["data"]["minAmount"],
            "max_amount": response["data"]["maxAmount"],
            "daily_limit": response["data"]["dailyLimit"],
            "monthly_limit": response["data"]["monthlyLimit"]
        }
    
    async def get_balance(self, currency: str = None) -> Dict:
        """
        Get merchant balance
        
        Args:
            currency: Optional currency code for specific balance
            
        Returns:
            Balance data
        """
        params = {"currency": currency} if currency else {}
        
        logger.info(f"Fetching BRICS Pay balance{f' for {currency}' if currency else ''}")
        
        response = await self._make_request("GET", "/v1/balance", params=params)
        
        if currency:
            return {
                "currency": currency,
                "available_balance": response["data"]["availableBalance"],
                "reserved_balance": response["data"]["reservedBalance"]
            }
        else:
            return {
                "balances": response["data"]["balances"]
            }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("BRICS Pay client closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
