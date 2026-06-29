"""
SEPA Payment Gateway Client - Production Implementation
Single Euro Payments Area
"""

import httpx
import logging
import re
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SEPAError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"SEPA Error {code}: {message}")

class SEPAClient:
    def __init__(self, api_key: str, creditor_id: str, creditor_iban: str, base_url: str = "https://api.sepa.eu"):
        self.api_key = api_key
        self.creditor_id = creditor_id
        self.creditor_iban = creditor_iban
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30)
        logger.info(f"SEPA client initialized for creditor: {creditor_id}")
    
    def _validate_iban(self, iban: str) -> bool:
        """Validate IBAN format"""
        iban = iban.replace(' ', '').upper()
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]+$', iban):
            return False
        return len(iban) >= 15 and len(iban) <= 34
    
    def _validate_bic(self, bic: str) -> bool:
        """Validate BIC format"""
        return bool(re.match(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$', bic.upper()))
    
    async def create_credit_transfer(self, debtor_iban: str, debtor_name: str, amount: float, currency: str, reference: str, remittance_info: str, debtor_bic: str = None) -> Dict:
        """Create SEPA Credit Transfer"""
        if not self._validate_iban(debtor_iban):
            raise SEPAError("INVALID_IBAN", f"Invalid debtor IBAN: {debtor_iban}")
        
        if not self._validate_iban(self.creditor_iban):
            raise SEPAError("INVALID_IBAN", f"Invalid creditor IBAN: {self.creditor_iban}")
        
        if debtor_bic and not self._validate_bic(debtor_bic):
            raise SEPAError("INVALID_BIC", f"Invalid BIC: {debtor_bic}")
        
        payload = {
            "creditorId": self.creditor_id,
            "creditorIBAN": self.creditor_iban,
            "debtorIBAN": debtor_iban,
            "debtorName": debtor_name,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "reference": reference,
            "remittanceInformation": remittance_info,
            "executionDate": datetime.utcnow().strftime("%Y-%m-%d")
        }
        
        if debtor_bic:
            payload["debtorBIC"] = debtor_bic
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/credit-transfers",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "accepted":
                raise SEPAError(
                    code=data.get("errorCode", "UNKNOWN"),
                    message=data.get("message", "Transfer failed"),
                    details=data
                )
            
            return {
                "transaction_id": data["transactionId"],
                "status": data["status"],
                "reference": reference,
                "amount": amount,
                "currency": currency,
                "execution_date": data.get("executionDate")
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"SEPA HTTP error: {e}")
            raise SEPAError(code=str(e.response.status_code), message=str(e))
        except Exception as e:
            logger.error(f"SEPA error: {e}")
            raise SEPAError(code="INTERNAL_ERROR", message=str(e))
    
    async def create_direct_debit(self, debtor_iban: str, debtor_name: str, amount: float, mandate_reference: str, remittance_info: str) -> Dict:
        """Create SEPA Direct Debit"""
        if not self._validate_iban(debtor_iban):
            raise SEPAError("INVALID_IBAN", f"Invalid debtor IBAN: {debtor_iban}")
        
        payload = {
            "creditorId": self.creditor_id,
            "creditorIBAN": self.creditor_iban,
            "debtorIBAN": debtor_iban,
            "debtorName": debtor_name,
            "amount": f"{amount:.2f}",
            "currency": "EUR",
            "mandateReference": mandate_reference,
            "remittanceInformation": remittance_info,
            "collectionDate": datetime.utcnow().strftime("%Y-%m-%d")
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/direct-debits",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "transaction_id": data["transactionId"],
                "status": data["status"],
                "mandate_reference": mandate_reference,
                "amount": amount,
                "collection_date": data.get("collectionDate")
            }
        except Exception as e:
            logger.error(f"Direct debit error: {e}")
            raise SEPAError(code="DEBIT_ERROR", message=str(e))
    
    async def get_transaction_status(self, transaction_id: str) -> Dict:
        """Get transaction status"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/transactions/{transaction_id}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "transaction_id": transaction_id,
                "status": data["status"],
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "execution_date": data.get("executionDate")
            }
        except Exception as e:
            logger.error(f"Status check error: {e}")
            raise SEPAError(code="STATUS_ERROR", message=str(e))
    
    async def validate_iban_api(self, iban: str) -> Dict:
        """Validate IBAN via API"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/validate/iban/{iban}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "iban": iban,
                "is_valid": data.get("valid", False),
                "bank_name": data.get("bankName"),
                "country": data.get("country")
            }
        except Exception as e:
            logger.error(f"IBAN validation error: {e}")
            return {"iban": iban, "is_valid": False}
    
    async def close(self):
        await self.client.aclose()
