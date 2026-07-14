"""
PIX Payment Gateway Client - Production Implementation
Brazilian instant payment system
"""

import httpx
import logging
import uuid
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PIXError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"PIX Error {code}: {message}")

class PIXClient:
    def __init__(self, client_id: str, client_secret: str, certificate_path: str, base_url: str = "https://api.pix.bcb.gov.br"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.certificate_path = certificate_path
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30, cert=certificate_path)
        self.access_token = None
        logger.info("PIX client initialized")
    
    async def _get_access_token(self) -> str:
        """Get OAuth2 access token"""
        if self.access_token:
            return self.access_token
        
        try:
            response = await self.client.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            return self.access_token
        except Exception as e:
            logger.error(f"Access token error: {e}")
            raise PIXError(code="AUTH_ERROR", message=str(e))
    
    async def create_qr_code(self, amount: float, description: str, payer_name: str = None, expiration_seconds: int = 3600) -> Dict:
        """Create PIX QR code for payment"""
        token = await self._get_access_token()
        txid = str(uuid.uuid4()).replace("-", "")
        
        payload = {
            "calendario": {
                "expiracao": expiration_seconds
            },
            "valor": {
                "original": f"{amount:.2f}"
            },
            "chave": self.client_id,
            "solicitacaoPagador": description
        }
        
        if payer_name:
            payload["devedor"] = {"nome": payer_name}
        
        try:
            response = await self.client.put(
                f"{self.base_url}/v2/cob/{txid}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "txid": data["txid"],
                "qr_code": data["pixCopiaECola"],
                "location": data["location"],
                "status": data["status"],
                "expiration": expiration_seconds
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"PIX HTTP error: {e}")
            raise PIXError(code=str(e.response.status_code), message=str(e))
        except Exception as e:
            logger.error(f"PIX error: {e}")
            raise PIXError(code="INTERNAL_ERROR", message=str(e))
    
    async def get_payment_status(self, txid: str) -> Dict:
        """Get PIX payment status"""
        token = await self._get_access_token()
        
        try:
            response = await self.client.get(
                f"{self.base_url}/v2/cob/{txid}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "txid": data["txid"],
                "status": data["status"],
                "amount": float(data["valor"]["original"]),
                "payer": data.get("devedor", {}).get("nome"),
                "payment_time": data.get("pix", [{}])[0].get("horario") if data.get("pix") else None
            }
        except Exception as e:
            logger.error(f"Get status error: {e}")
            raise PIXError(code="STATUS_ERROR", message=str(e))
    
    async def send_pix(self, pix_key: str, amount: float, description: str) -> Dict:
        """Send PIX payment to key"""
        token = await self._get_access_token()
        
        payload = {
            "chave": pix_key,
            "valor": f"{amount:.2f}",
            "descricao": description
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/v2/pix",
                json=payload,
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "end_to_end_id": data["endToEndId"],
                "txid": data.get("txid"),
                "amount": amount,
                "status": "completed"
            }
        except Exception as e:
            logger.error(f"Send PIX error: {e}")
            raise PIXError(code="SEND_ERROR", message=str(e))
    
    async def validate_pix_key(self, pix_key: str) -> Dict:
        """Validate PIX key"""
        token = await self._get_access_token()
        
        try:
            response = await self.client.get(
                f"{self.base_url}/v2/dict/key/{pix_key}",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "pix_key": pix_key,
                "key_type": data["tipo"],
                "account_holder": data["nome"],
                "is_valid": True
            }
        except Exception as e:
            logger.error(f"Validate key error: {e}")
            return {"pix_key": pix_key, "is_valid": False}
    
    async def close(self):
        await self.client.aclose()
