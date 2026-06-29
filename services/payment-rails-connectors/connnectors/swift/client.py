"""
SWIFT (Society for Worldwide Interbank Financial Telecommunication) Payment Gateway Client
Production-ready implementation for international wire transfers
"""

import httpx
import logging
import re
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class SWIFTMessageType(Enum):
    MT103 = "MT103"  # Single Customer Credit Transfer
    MT202 = "MT202"  # Financial Institution Transfer
    MT900 = "MT900"  # Confirmation of Debit
    MT910 = "MT910"  # Confirmation of Credit

class SWIFTError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"SWIFT Error {code}: {message}")

class SWIFTClient:
    def __init__(self, api_key: str, bic_code: str, base_url: str = "https://api.swift.com", timeout: int = 60):
        self.api_key = api_key
        self.bic_code = bic_code
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"SWIFT client initialized for BIC: {bic_code}")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-SWIFT-BIC": self.bic_code
        }
    
    def _validate_bic(self, bic: str) -> bool:
        """Validate BIC code format (8 or 11 characters)"""
        pattern = r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$'
        return bool(re.match(pattern, bic.upper()))
    
    def _validate_iban(self, iban: str) -> bool:
        """Basic IBAN validation"""
        iban = iban.replace(' ', '').upper()
        return len(iban) >= 15 and len(iban) <= 34 and iban[:2].isalpha()
    
    async def initiate_wire_transfer(
        self, 
        sender_account: str, 
        receiver_account: str, 
        receiver_bic: str, 
        amount: float, 
        currency: str, 
        purpose: str, 
        reference: str,
        receiver_name: str = None,
        sender_name: str = None,
        intermediary_bic: str = None,
        charge_bearer: str = "SHA"  # SHA (Shared), OUR (Sender), BEN (Receiver)
    ) -> Dict:
        """Initiate SWIFT wire transfer (MT103)"""
        
        if not self._validate_bic(receiver_bic):
            raise SWIFTError("INVALID_BIC", f"Invalid receiver BIC: {receiver_bic}")
        
        if intermediary_bic and not self._validate_bic(intermediary_bic):
            raise SWIFTError("INVALID_BIC", f"Invalid intermediary BIC: {intermediary_bic}")
        
        payload = {
            "messageType": "MT103",
            "sender": {
                "bic": self.bic_code,
                "account": sender_account,
                "name": sender_name
            },
            "receiver": {
                "bic": receiver_bic,
                "account": receiver_account,
                "name": receiver_name
            },
            "transaction": {
                "amount": f"{amount:.2f}",
                "currency": currency,
                "reference": reference,
                "purpose": purpose,
                "chargeBearer": charge_bearer,
                "valueDate": datetime.utcnow().strftime("%Y%m%d")
            }
        }
        
        if intermediary_bic:
            payload["intermediary"] = {"bic": intermediary_bic}
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/payments/wire-transfer",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "rejected":
                raise SWIFTError(
                    code=data.get("errorCode", "REJECTED"),
                    message=data.get("errorMessage", "Transfer rejected"),
                    details=data
                )
            
            return {
                "transaction_id": data.get("transactionId"),
                "uetr": data.get("uetr"),  # Unique End-to-End Transaction Reference
                "status": data.get("status"),
                "amount": amount,
                "currency": currency,
                "reference": reference,
                "estimated_delivery": data.get("estimatedDelivery")
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"SWIFT HTTP error: {e}")
            raise SWIFTError(code=str(e.response.status_code), message=str(e))
        except Exception as e:
            logger.error(f"SWIFT error: {e}")
            raise SWIFTError(code="INTERNAL_ERROR", message=str(e))
    
    async def get_transfer_status(self, transaction_id: str = None, uetr: str = None) -> Dict:
        """Get transfer status by transaction ID or UETR"""
        if not transaction_id and not uetr:
            raise SWIFTError("INVALID_REQUEST", "Either transaction_id or uetr must be provided")
        
        try:
            if uetr:
                response = await self.client.get(
                    f"{self.base_url}/v1/payments/uetr/{uetr}",
                    headers=self._get_headers()
                )
            else:
                response = await self.client.get(
                    f"{self.base_url}/v1/payments/{transaction_id}/status",
                    headers=self._get_headers()
                )
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "transaction_id": data.get("transactionId"),
                "uetr": data.get("uetr"),
                "status": data.get("status"),
                "current_location": data.get("currentLocation"),
                "last_update": data.get("lastUpdate")
            }
        except Exception as e:
            logger.error(f"Get status error: {e}")
            raise SWIFTError(code="STATUS_ERROR", message=str(e))
    
    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Dict:
        """Get SWIFT exchange rate"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/rates",
                params={"from": from_currency, "to": to_currency},
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": data.get("rate"),
                "timestamp": data.get("timestamp")
            }
        except Exception as e:
            logger.error(f"Exchange rate error: {e}")
            raise SWIFTError(code="RATE_ERROR", message=str(e))
    
    async def validate_bic_code(self, bic: str) -> Dict:
        """Validate and get BIC code details"""
        if not self._validate_bic(bic):
            raise SWIFTError("INVALID_BIC", f"Invalid BIC format: {bic}")
        
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/bic/{bic}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "bic": bic,
                "institution_name": data.get("institutionName"),
                "branch": data.get("branch"),
                "city": data.get("city"),
                "country": data.get("country"),
                "is_active": data.get("isActive")
            }
        except Exception as e:
            logger.error(f"BIC validation error: {e}")
            raise SWIFTError(code="BIC_ERROR", message=str(e))
    
    async def get_transaction_fees(self, amount: float, currency: str, destination_country: str) -> Dict:
        """Get estimated transaction fees"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/fees",
                params={
                    "amount": amount,
                    "currency": currency,
                    "destinationCountry": destination_country
                },
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "amount": amount,
                "currency": currency,
                "swift_fee": data.get("swiftFee"),
                "correspondent_fee": data.get("correspondentFee"),
                "total_fee": data.get("totalFee")
            }
        except Exception as e:
            logger.error(f"Get fees error: {e}")
            raise SWIFTError(code="FEES_ERROR", message=str(e))
    
    async def cancel_transfer(self, transaction_id: str, reason: str) -> Dict:
        """Request transfer cancellation"""
        payload = {
            "transactionId": transaction_id,
            "reason": reason
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/payments/{transaction_id}/cancel",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "transaction_id": transaction_id,
                "cancellation_status": data.get("status"),
                "message": data.get("message")
            }
        except Exception as e:
            logger.error(f"Cancel transfer error: {e}")
            raise SWIFTError(code="CANCEL_ERROR", message=str(e))
    
    async def close(self):
        await self.client.aclose()
