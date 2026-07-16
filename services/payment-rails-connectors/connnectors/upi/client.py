"""
UPI Payment Gateway Client - Production Implementation
Unified Payments Interface (India)
"""

import httpx
import hashlib
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class UPIError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"UPI Error {code}: {message}")

class UPIClient:
    def __init__(self, merchant_id: str, merchant_key: str, vpa: str, base_url: str = "https://api.upi.npci.org.in"):
        self.merchant_id = merchant_id
        self.merchant_key = merchant_key
        self.vpa = vpa
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30)
        logger.info(f"UPI client initialized for VPA: {vpa}")
    
    def _generate_checksum(self, data: str) -> str:
        """Generate SHA256 checksum"""
        return hashlib.sha256(f"{data}{self.merchant_key}".encode()).hexdigest()
    
    async def collect_request(self, payer_vpa: str, amount: float, note: str, reference_id: str) -> Dict:
        """Initiate UPI collect request"""
        data_str = f"{self.merchant_id}{payer_vpa}{amount}{reference_id}"
        checksum = self._generate_checksum(data_str)
        
        payload = {
            "merchantId": self.merchant_id,
            "merchantVPA": self.vpa,
            "payerVPA": payer_vpa,
            "amount": f"{amount:.2f}",
            "note": note,
            "referenceId": reference_id,
            "checksum": checksum
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/collect",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "SUCCESS":
                raise UPIError(
                    code=data.get("errorCode", "UNKNOWN"),
                    message=data.get("message", "Collect request failed"),
                    details=data
                )
            
            return {
                "txn_id": data["txnId"],
                "reference_id": reference_id,
                "status": data["status"],
                "amount": amount,
                "payer_vpa": payer_vpa
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"UPI HTTP error: {e}")
            raise UPIError(code=str(e.response.status_code), message=str(e))
        except Exception as e:
            logger.error(f"UPI error: {e}")
            raise UPIError(code="INTERNAL_ERROR", message=str(e))
    
    async def check_status(self, reference_id: str) -> Dict:
        """Check transaction status"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v1/status/{reference_id}",
                headers={"X-Merchant-ID": self.merchant_id}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "reference_id": reference_id,
                "txn_id": data.get("txnId"),
                "status": data["status"],
                "amount": data.get("amount"),
                "timestamp": data.get("timestamp")
            }
        except Exception as e:
            logger.error(f"Status check error: {e}")
            raise UPIError(code="STATUS_ERROR", message=str(e))
    
    async def validate_vpa(self, vpa: str) -> Dict:
        """Validate UPI VPA"""
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/validate",
                json={"vpa": vpa, "merchantId": self.merchant_id}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "vpa": vpa,
                "is_valid": data.get("valid", False),
                "name": data.get("name"),
                "bank": data.get("bank")
            }
        except Exception as e:
            logger.error(f"VPA validation error: {e}")
            return {"vpa": vpa, "is_valid": False}
    
    async def generate_qr(self, amount: float, note: str, reference_id: str) -> Dict:
        """Generate UPI QR code"""
        upi_string = f"upi://pay?pa={self.vpa}&pn=Merchant&am={amount:.2f}&tn={note}&tr={reference_id}"
        
        return {
            "qr_string": upi_string,
            "reference_id": reference_id,
            "amount": amount,
            "vpa": self.vpa
        }
    
    async def refund(self, original_txn_id: str, amount: float, reason: str) -> Dict:
        """Initiate refund"""
        payload = {
            "merchantId": self.merchant_id,
            "originalTxnId": original_txn_id,
            "refundAmount": f"{amount:.2f}",
            "reason": reason
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/refund",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "refund_id": data["refundId"],
                "original_txn_id": original_txn_id,
                "status": data["status"],
                "amount": amount
            }
        except Exception as e:
            logger.error(f"Refund error: {e}")
            raise UPIError(code="REFUND_ERROR", message=str(e))
    
    async def close(self):
        await self.client.aclose()
