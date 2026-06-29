"""
BRICS Pay Payment Gateway Client - Production Implementation
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
    BRL = "BRL"  # Brazilian Real
    RUB = "RUB"  # Russian Ruble
    INR = "INR"  # Indian Rupee
    CNY = "CNY"  # Chinese Yuan
    ZAR = "ZAR"  # South African Rand

class BRICSPayError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"BRICS Pay Error {code}: {message}")

class BRICSPayClient:
    """
    BRICS Pay Gateway Client
    Facilitates payments across BRICS nations using local currencies
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        merchant_id: str,
        base_url: str = "https://api.brics-pay.com",
        timeout: int = 30
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.merchant_id = merchant_id
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"BRICS Pay client initialized for merchant: {merchant_id}")
    
    def _generate_signature(self, payload: Dict) -> str:
        """Generate HMAC-SHA256 signature for request"""
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self, signature: str = None) -> Dict[str, str]:
        headers = {
            "X-API-Key": self.api_key,
            "X-Merchant-ID": self.merchant_id,
            "Content-Type": "application/json"
        }
        if signature:
            headers["X-Signature"] = signature
        return headers
    
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
        """Initiate cross-border BRICS transfer"""
        
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
        
        signature = self._generate_signature(payload)
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/transfers",
                json=payload,
                headers=self._get_headers(signature)
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                raise BRICSPayError(
                    code=data.get("errorCode", "UNKNOWN"),
                    message=data.get("message", "Transfer failed"),
                    details=data
                )
            
            return {
                "transfer_id": data["data"]["transferId"],
                "status": data["data"]["status"],
                "reference": data["data"]["reference"],
                "source_amount": amount,
                "source_currency": source_currency,
                "destination_amount": data["data"]["destinationAmount"],
                "destination_currency": destination_currency,
                "exchange_rate": data["data"]["exchangeRate"],
                "fee": data["data"].get("fee", 0),
                "estimated_delivery": data["data"].get("estimatedDelivery")
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"BRICS Pay HTTP error: {e}")
            raise BRICSPayError(code=str(e.response.status_code), message=str(e))
        except Exception as e:
            logger.error(f"BRICS Pay error: {e}")
            raise BRICSPayError(code="INTERNAL_ERROR", message=str(e))
    
    async def get_transfer_status(self, transfer_id: str) -> Dict:
        """Get transfer status"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/transfers/{transfer_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "transfer_id": transfer_id,
                "status": data["data"]["status"],
                "reference": data["data"].get("reference"),
                "source_amount": data["data"].get("sourceAmount"),
                "destination_amount": data["data"].get("destinationAmount"),
                "current_stage": data["data"].get("currentStage"),
                "updated_at": data["data"].get("updatedAt")
            }
        except Exception as e:
            logger.error(f"Get status error: {e}")
            raise BRICSPayError(code="STATUS_ERROR", message=str(e))
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        amount: float = None
    ) -> Dict:
        """Get real-time exchange rate between BRICS currencies"""
        params = {
            "from": from_currency,
            "to": to_currency
        }
        if amount:
            params["amount"] = amount
        
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/rates",
                params=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": data["data"]["rate"],
                "inverse_rate": data["data"].get("inverseRate"),
                "timestamp": data["data"]["timestamp"]
            }
        except Exception as e:
            logger.error(f"Exchange rate error: {e}")
            raise BRICSPayError(code="RATE_ERROR", message=str(e))
    
    async def verify_account(
        self,
        account_number: str,
        country_code: str,
        currency: str
    ) -> Dict:
        """Verify beneficiary account in BRICS country"""
        payload = {
            "accountNumber": account_number,
            "countryCode": country_code,
            "currency": currency
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/accounts/verify",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "account_number": account_number,
                "account_name": data["data"]["accountName"],
                "bank_name": data["data"]["bankName"],
                "country_code": country_code,
                "is_valid": data["data"]["isValid"]
            }
        except Exception as e:
            logger.error(f"Account verification error: {e}")
            raise BRICSPayError(code="VERIFY_ERROR", message=str(e))
    
    async def get_supported_corridors(self) -> List[Dict]:
        """Get list of supported payment corridors"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/corridors",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return data["data"]["corridors"]
        except Exception as e:
            logger.error(f"Get corridors error: {e}")
            raise BRICSPayError(code="CORRIDORS_ERROR", message=str(e))
    
    async def get_transaction_limits(
        self,
        source_currency: str,
        destination_currency: str
    ) -> Dict:
        """Get transaction limits for currency pair"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/limits",
                params={
                    "sourceCurrency": source_currency,
                    "destinationCurrency": destination_currency
                },
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "source_currency": source_currency,
                "destination_currency": destination_currency,
                "min_amount": data["data"]["minAmount"],
                "max_amount": data["data"]["maxAmount"],
                "daily_limit": data["data"]["dailyLimit"],
                "monthly_limit": data["data"]["monthlyLimit"]
            }
        except Exception as e:
            logger.error(f"Get limits error: {e}")
            raise BRICSPayError(code="LIMITS_ERROR", message=str(e))
    
    async def get_balance(self, currency: str = None) -> Dict:
        """Get merchant balance"""
        params = {"currency": currency} if currency else {}
        
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/balance",
                params=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            if currency:
                return {
                    "currency": currency,
                    "available_balance": data["data"]["availableBalance"],
                    "reserved_balance": data["data"]["reservedBalance"]
                }
            else:
                return {
                    "balances": data["data"]["balances"]
                }
        except Exception as e:
            logger.error(f"Get balance error: {e}")
            raise BRICSPayError(code="BALANCE_ERROR", message=str(e))
    
    async def close(self):
        await self.client.aclose()
