"""
PAPSS (Pan-African Payment and Settlement System) Client - Production Implementation
"""

import httpx
import hashlib
import hmac
import logging
from typing import Dict, Optional, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class PAPSSError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"PAPSS Error {code}: {message}")

class PAPSSClient:
    def __init__(self, api_key: str, secret_key: str, institution_id: str, base_url: str = "https://api.papss.com"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.institution_id = institution_id
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30)
        logger.info(f"PAPSS client initialized for institution: {institution_id}")
    
    def _generate_signature(self, payload: Dict) -> str:
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
            "X-Institution-ID": self.institution_id,
            "Content-Type": "application/json"
        }
        if signature:
            headers["X-Signature"] = signature
        return headers
    
    async def initiate_transfer(self, source_account: str, destination_account: str, amount: float, currency: str, destination_currency: str, beneficiary_name: str, reference: str, narration: str) -> Dict:
        """Initiate cross-border transfer"""
        payload = {
            "sourceAccount": source_account,
            "destinationAccount": destination_account,
            "amount": amount,
            "sourceCurrency": currency,
            "destinationCurrency": destination_currency,
            "beneficiaryName": beneficiary_name,
            "reference": reference,
            "narration": narration,
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
                raise PAPSSError(
                    code=data.get("errorCode", "UNKNOWN"),
                    message=data.get("message", "Transfer failed"),
                    details=data
                )
            
            return {
                "transfer_id": data["data"]["transferId"],
                "status": data["data"]["status"],
                "reference": data["data"]["reference"],
                "amount": amount,
                "currency": currency,
                "exchange_rate": data["data"].get("exchangeRate"),
                "fee": data["data"].get("fee", 0)
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"PAPSS HTTP error: {e}")
            raise PAPSSError(code=str(e.response.status_code), message=str(e))
        except Exception as e:
            logger.error(f"PAPSS error: {e}")
            raise PAPSSError(code="INTERNAL_ERROR", message=str(e))
    
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
                "amount": data["data"].get("amount"),
                "currency": data["data"].get("currency")
            }
        except Exception as e:
            logger.error(f"Get status error: {e}")
            raise PAPSSError(code="STATUS_ERROR", message=str(e))
    
    async def get_exchange_rate(self, source_currency: str, destination_currency: str, amount: float) -> Dict:
        """Get exchange rate"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/rates",
                params={
                    "sourceCurrency": source_currency,
                    "destinationCurrency": destination_currency,
                    "amount": amount
                },
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "source_currency": source_currency,
                "destination_currency": destination_currency,
                "rate": data["data"]["rate"],
                "amount": amount,
                "converted_amount": data["data"]["convertedAmount"]
            }
        except Exception as e:
            logger.error(f"Exchange rate error: {e}")
            raise PAPSSError(code="RATE_ERROR", message=str(e))
    
    async def verify_account(self, account_number: str, bank_code: str, country_code: str) -> Dict:
        """Verify beneficiary account"""
        payload = {
            "accountNumber": account_number,
            "bankCode": bank_code,
            "countryCode": country_code
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
                "bank_code": bank_code,
                "bank_name": data["data"]["bankName"],
                "country_code": country_code
            }
        except Exception as e:
            logger.error(f"Account verification error: {e}")
            raise PAPSSError(code="VERIFY_ERROR", message=str(e))
    
    async def get_participating_banks(self, country_code: str) -> List[Dict]:
        """Get list of participating banks"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/banks",
                params={"countryCode": country_code},
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return data["data"]["banks"]
        except Exception as e:
            logger.error(f"Get banks error: {e}")
            raise PAPSSError(code="BANKS_ERROR", message=str(e))
    
    async def close(self):
        await self.client.aclose()
