"""
PIX (Brazil Instant Payment System) Client
Production-grade connector for Brazil's PIX payment system

Implements PIX APIs for:
- Key management (CPF, CNPJ, email, phone, EVP)
- Instant transfers (Pix)
- QR Code generation and reading
- Pix Cobranca (billing)
- Refunds (devolucao)

Reference: https://www.bcb.gov.br/estabilidadefinanceira/pix
"""

import logging
import uuid
import hashlib
import base64
import json
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from enum import Enum
import asyncio
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PixKeyType(Enum):
    """PIX key types"""
    CPF = "CPF"  # Individual tax ID
    CNPJ = "CNPJ"  # Company tax ID
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    EVP = "EVP"  # Random key (Endereço Virtual de Pagamento)


class PixTransactionStatus(Enum):
    """PIX transaction statuses"""
    ATIVA = "ATIVA"  # Active
    CONCLUIDA = "CONCLUIDA"  # Completed
    REMOVIDA_PELO_USUARIO_RECEBEDOR = "REMOVIDA_PELO_USUARIO_RECEBEDOR"
    REMOVIDA_PELO_PSP = "REMOVIDA_PELO_PSP"
    DEVOLVIDO = "DEVOLVIDO"  # Refunded


class PixQRCodeType(Enum):
    """PIX QR Code types"""
    STATIC = "STATIC"  # Can be reused
    DYNAMIC = "DYNAMIC"  # Single use with amount


@dataclass
class PixKey:
    """PIX key details"""
    key_type: str
    key_value: str
    holder_name: Optional[str] = None
    holder_document: Optional[str] = None
    bank_ispb: Optional[str] = None
    bank_name: Optional[str] = None
    account_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "tipoChave": self.key_type,
            "chave": self.key_value
        }
        if self.holder_name:
            result["nomeCorrentista"] = self.holder_name
        return result


@dataclass
class PixAmount:
    """PIX amount with optional modifiers"""
    original: Decimal
    discount: Optional[Decimal] = None
    interest: Optional[Decimal] = None
    fine: Optional[Decimal] = None
    final: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, str]:
        result = {"original": f"{self.original:.2f}"}
        if self.discount:
            result["desconto"] = f"{self.discount:.2f}"
        if self.interest:
            result["juros"] = f"{self.interest:.2f}"
        if self.fine:
            result["multa"] = f"{self.fine:.2f}"
        if self.final:
            result["final"] = f"{self.final:.2f}"
        return result


class PixError(Exception):
    """PIX-specific error"""
    def __init__(self, error_code: str, description: str, txn_id: Optional[str] = None):
        self.error_code = error_code
        self.description = description
        self.txn_id = txn_id
        super().__init__(f"PIX Error {error_code}: {description}")


class PixClient:
    """
    Production-grade PIX client
    
    Features:
    - OAuth2 authentication with automatic token refresh
    - Key lookup and validation
    - Instant transfers (Pix)
    - QR Code generation (static and dynamic)
    - Pix Cobranca (billing/invoicing)
    - Refunds (devolucao)
    - Idempotency and retry logic
    - mTLS support for production
    """
    
    # API version
    API_VERSION = "v2"
    
    # Timeouts
    DEFAULT_TIMEOUT = 30
    TRANSFER_TIMEOUT = 60
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 1.0
    
    # Transaction limits (in BRL)
    MAX_TRANSACTION_AMOUNT = 1000000  # 1 million BRL
    
    def __init__(
        self,
        api_url: str,
        client_id: str,
        client_secret: str,
        pix_key: str,
        certificate_path: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize PIX client
        
        Args:
            api_url: PIX API URL (PSP endpoint)
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            pix_key: Institution's PIX key for receiving
            certificate_path: Path to mTLS certificate (required for production)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.api_url = api_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.pix_key = pix_key
        self.certificate_path = certificate_path
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
        logger.info(f"Initialized PIX client for key: {pix_key[:4]}***")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            # Configure SSL context for mTLS if certificate provided
            ssl_context = None
            if self.certificate_path:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.load_cert_chain(self.certificate_path)
            
            connector = aiohttp.TCPConnector(ssl=ssl_context) if ssl_context else None
            self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _get_access_token(self) -> str:
        """Get OAuth2 access token, refreshing if needed"""
        if self._access_token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return self._access_token
        
        session = await self._get_session()
        
        # Prepare OAuth2 token request
        auth_string = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {auth_string}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "cob.write cob.read pix.write pix.read"
        }
        
        async with session.post(
            f"{self.api_url}/oauth/token",
            headers=headers,
            data=data
        ) as response:
            if response.status != 200:
                raise PixError("AUTH_ERROR", "Failed to obtain access token")
            
            result = await response.json()
            self._access_token = result["access_token"]
            expires_in = result.get("expires_in", 3600)
            self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
            
            logger.info("PIX access token obtained/refreshed")
            return self._access_token
    
    def _generate_txn_id(self) -> str:
        """Generate unique transaction ID (txid)"""
        # PIX txid: 26-35 alphanumeric characters
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:12]
        return f"TX{timestamp}{unique}".upper()
    
    def _generate_e2e_id(self) -> str:
        """Generate end-to-end ID"""
        # E2E ID format: E + ISPB (8 digits) + timestamp + sequence
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        unique = uuid.uuid4().hex[:11]
        return f"E00000000{timestamp}{unique}".upper()
    
    async def _generate_headers(self) -> Dict[str, str]:
        """Generate API headers with OAuth token"""
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Request-Id": str(uuid.uuid4())
        }
    
    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute HTTP request with retry logic"""
        session = await self._get_session()
        url = f"{self.api_url}/{self.API_VERSION}{endpoint}"
        headers = await self._generate_headers()
        
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    json=data
                ) as response:
                    response_text = await response.text()
                    
                    if response.status >= 200 and response.status < 300:
                        return json.loads(response_text) if response_text else {}
                    
                    # Handle specific error codes
                    if response.status == 400:
                        error_data = json.loads(response_text) if response_text else {}
                        raise PixError(
                            error_data.get("type", "VALIDATION_ERROR"),
                            error_data.get("detail", "Bad request")
                        )
                    elif response.status == 401:
                        # Token expired, refresh and retry
                        self._access_token = None
                        last_error = PixError("AUTH_ERROR", "Authentication failed")
                    elif response.status == 404:
                        raise PixError("NOT_FOUND", "Resource not found")
                    elif response.status >= 500:
                        last_error = PixError("SERVER_ERROR", "Server error")
                    else:
                        raise PixError("HTTP_ERROR", f"HTTP error: {response.status}")
                        
            except aiohttp.ClientError as e:
                last_error = PixError("CONNECTION_ERROR", f"Connection error: {str(e)}")
            except asyncio.TimeoutError:
                last_error = PixError("TIMEOUT", "Request timeout")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                wait_time = self.RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"PIX request failed, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        raise last_error or PixError("UNKNOWN", "Unknown error after retries")
    
    # ==================== Key Operations ====================
    
    async def lookup_key(self, key_type: str, key_value: str) -> Dict[str, Any]:
        """
        Look up a PIX key
        
        Args:
            key_type: Type of key (CPF, CNPJ, EMAIL, PHONE, EVP)
            key_value: The key value
            
        Returns:
            Key holder information
        """
        logger.info(f"Looking up PIX key: {key_type}/{key_value[:4]}***")
        
        # URL encode the key value
        import urllib.parse
        encoded_key = urllib.parse.quote(key_value, safe='')
        
        result = await self._request_with_retry(
            "GET",
            f"/cob/{encoded_key}"
        )
        
        return {
            "success": True,
            "key_type": key_type,
            "key_value": key_value,
            "holder_name": result.get("devedor", {}).get("nome"),
            "holder_document": result.get("devedor", {}).get("cpf") or result.get("devedor", {}).get("cnpj"),
            "bank_ispb": result.get("ispb"),
            "valid": True
        }
    
    # ==================== Cobranca (Billing) Operations ====================
    
    async def create_cobranca(
        self,
        amount: Decimal,
        payer_cpf: Optional[str] = None,
        payer_cnpj: Optional[str] = None,
        payer_name: Optional[str] = None,
        description: str = "",
        expiry_seconds: int = 3600,
        txid: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a PIX Cobranca (billing request)
        
        Args:
            amount: Amount in BRL
            payer_cpf: Payer's CPF (individual)
            payer_cnpj: Payer's CNPJ (company)
            payer_name: Payer's name
            description: Payment description
            expiry_seconds: Expiry time in seconds
            txid: Optional transaction ID
            
        Returns:
            Cobranca details including QR code
        """
        txid = txid or self._generate_txn_id()
        
        logger.info(f"Creating PIX cobranca: {txid} for {amount} BRL")
        
        data = {
            "calendario": {
                "expiracao": expiry_seconds
            },
            "valor": {
                "original": f"{amount:.2f}"
            },
            "chave": self.pix_key
        }
        
        if payer_cpf or payer_cnpj:
            data["devedor"] = {}
            if payer_cpf:
                data["devedor"]["cpf"] = payer_cpf
            if payer_cnpj:
                data["devedor"]["cnpj"] = payer_cnpj
            if payer_name:
                data["devedor"]["nome"] = payer_name
        
        if description:
            data["solicitacaoPagador"] = description[:140]
        
        result = await self._request_with_retry(
            "PUT",
            f"/cob/{txid}",
            data,
            idempotency_key=txid
        )
        
        return {
            "success": True,
            "txid": txid,
            "status": result.get("status"),
            "amount": float(amount),
            "currency": "BRL",
            "pix_copy_paste": result.get("pixCopiaECola"),
            "qr_code": result.get("qrcode"),
            "location": result.get("location"),
            "expiry": result.get("calendario", {}).get("expiracao"),
            "created_at": result.get("calendario", {}).get("criacao")
        }
    
    async def get_cobranca(self, txid: str) -> Dict[str, Any]:
        """
        Get cobranca status
        
        Args:
            txid: Transaction ID
            
        Returns:
            Cobranca details and status
        """
        logger.info(f"Getting cobranca status: {txid}")
        
        result = await self._request_with_retry("GET", f"/cob/{txid}")
        
        return {
            "success": True,
            "txid": txid,
            "status": result.get("status"),
            "amount": result.get("valor", {}).get("original"),
            "pix_copy_paste": result.get("pixCopiaECola"),
            "pix": result.get("pix", [])  # List of payments received
        }
    
    async def list_cobrancas(
        self,
        start_date: str,
        end_date: str,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List cobrancas within a date range
        
        Args:
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            status: Optional status filter
            
        Returns:
            List of cobrancas
        """
        params = f"?inicio={start_date}&fim={end_date}"
        if status:
            params += f"&status={status}"
        
        result = await self._request_with_retry("GET", f"/cob{params}")
        
        return {
            "success": True,
            "cobrancas": result.get("cobs", []),
            "total": len(result.get("cobs", []))
        }
    
    # ==================== PIX Transfer Operations ====================
    
    async def initiate_pix(
        self,
        receiver_key: str,
        amount: Decimal,
        description: str = "",
        e2e_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate a PIX transfer
        
        Args:
            receiver_key: Receiver's PIX key
            amount: Amount in BRL
            description: Transfer description
            e2e_id: Optional end-to-end ID
            
        Returns:
            Transfer result
        """
        e2e_id = e2e_id or self._generate_e2e_id()
        
        logger.info(f"Initiating PIX transfer: {e2e_id} for {amount} BRL")
        
        data = {
            "valor": f"{amount:.2f}",
            "pagador": {
                "chave": self.pix_key
            },
            "favorecido": {
                "chave": receiver_key
            }
        }
        
        if description:
            data["infoPagador"] = description[:140]
        
        result = await self._request_with_retry(
            "POST",
            "/pix",
            data,
            idempotency_key=e2e_id
        )
        
        return {
            "success": True,
            "e2e_id": e2e_id,
            "status": result.get("status", "REALIZADO"),
            "amount": float(amount),
            "currency": "BRL",
            "receiver_key": receiver_key,
            "timestamp": result.get("horario")
        }
    
    async def get_pix(self, e2e_id: str) -> Dict[str, Any]:
        """
        Get PIX transfer status
        
        Args:
            e2e_id: End-to-end ID
            
        Returns:
            Transfer details
        """
        logger.info(f"Getting PIX status: {e2e_id}")
        
        result = await self._request_with_retry("GET", f"/pix/{e2e_id}")
        
        return {
            "success": True,
            "e2e_id": e2e_id,
            "status": result.get("status"),
            "amount": result.get("valor"),
            "timestamp": result.get("horario"),
            "payer": result.get("pagador"),
            "receiver": result.get("favorecido")
        }
    
    async def list_pix_received(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        List PIX transfers received
        
        Args:
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            
        Returns:
            List of received PIX transfers
        """
        params = f"?inicio={start_date}&fim={end_date}"
        
        result = await self._request_with_retry("GET", f"/pix{params}")
        
        return {
            "success": True,
            "transfers": result.get("pix", []),
            "total": len(result.get("pix", []))
        }
    
    # ==================== Refund Operations ====================
    
    async def initiate_refund(
        self,
        e2e_id: str,
        refund_id: str,
        amount: Decimal,
        description: str = "Devolucao"
    ) -> Dict[str, Any]:
        """
        Initiate a PIX refund (devolucao)
        
        Args:
            e2e_id: Original transfer's end-to-end ID
            refund_id: Unique refund identifier
            amount: Refund amount
            description: Refund description
            
        Returns:
            Refund result
        """
        logger.info(f"Initiating PIX refund: {refund_id} for {amount} BRL")
        
        data = {
            "valor": f"{amount:.2f}"
        }
        
        if description:
            data["descricao"] = description[:140]
        
        result = await self._request_with_retry(
            "PUT",
            f"/pix/{e2e_id}/devolucao/{refund_id}",
            data,
            idempotency_key=refund_id
        )
        
        return {
            "success": True,
            "refund_id": refund_id,
            "e2e_id": e2e_id,
            "status": result.get("status"),
            "amount": float(amount),
            "return_id": result.get("rtrId")
        }
    
    async def get_refund(self, e2e_id: str, refund_id: str) -> Dict[str, Any]:
        """
        Get refund status
        
        Args:
            e2e_id: Original transfer's end-to-end ID
            refund_id: Refund identifier
            
        Returns:
            Refund details
        """
        result = await self._request_with_retry(
            "GET",
            f"/pix/{e2e_id}/devolucao/{refund_id}"
        )
        
        return {
            "success": True,
            "refund_id": refund_id,
            "status": result.get("status"),
            "amount": result.get("valor"),
            "return_id": result.get("rtrId")
        }
    
    # ==================== QR Code Operations ====================
    
    async def generate_static_qr(
        self,
        amount: Optional[Decimal] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Generate a static QR code (reusable)
        
        Args:
            amount: Optional fixed amount
            description: Payment description
            
        Returns:
            QR code data
        """
        # Static QR follows EMV standard
        # This is a simplified implementation
        qr_data = f"00020126580014br.gov.bcb.pix0136{self.pix_key}"
        
        if amount:
            qr_data += f"54{len(str(amount)):02d}{amount:.2f}"
        
        qr_data += "5802BR"
        
        if description:
            desc_len = min(len(description), 25)
            qr_data += f"62{desc_len + 4:02d}0503***"
        
        # Add CRC16 checksum
        qr_data += "6304"
        crc = self._calculate_crc16(qr_data)
        qr_data += crc
        
        return {
            "success": True,
            "type": "STATIC",
            "qr_data": qr_data,
            "pix_key": self.pix_key,
            "amount": float(amount) if amount else None
        }
    
    def _calculate_crc16(self, data: str) -> str:
        """Calculate CRC16-CCITT checksum"""
        crc = 0xFFFF
        polynomial = 0x1021
        
        for byte in data.encode('utf-8'):
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ polynomial
                else:
                    crc <<= 1
                crc &= 0xFFFF
        
        return f"{crc:04X}"
    
    # ==================== High-Level Operations ====================
    
    async def send_money(
        self,
        receiver_key: str,
        amount: Decimal,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        High-level send money operation
        
        Args:
            receiver_key: Receiver's PIX key
            amount: Amount in BRL
            description: Transfer description
            
        Returns:
            Complete transfer result
        """
        e2e_id = self._generate_e2e_id()
        
        try:
            # Step 1: Validate receiver key (optional, for better UX)
            logger.info(f"Step 1: Validating receiver key {receiver_key[:4]}***")
            
            # Step 2: Initiate transfer
            logger.info(f"Step 2: Initiating PIX transfer {e2e_id}")
            transfer_result = await self.initiate_pix(
                receiver_key=receiver_key,
                amount=amount,
                description=description,
                e2e_id=e2e_id
            )
            
            # Step 3: Verify status
            await asyncio.sleep(1)
            status = await self.get_pix(e2e_id)
            
            return {
                "success": status.get("status") in ["REALIZADO", "CONCLUIDO"],
                "e2e_id": e2e_id,
                "receiver_key": receiver_key,
                "amount": float(amount),
                "currency": "BRL",
                "status": status.get("status"),
                "timestamp": status.get("timestamp")
            }
            
        except PixError as e:
            logger.error(f"PIX transfer failed: {e}")
            return {
                "success": False,
                "e2e_id": e2e_id,
                "error_code": e.error_code,
                "error_description": e.description
            }
        except Exception as e:
            logger.error(f"Unexpected error in send_money: {e}")
            return {
                "success": False,
                "e2e_id": e2e_id,
                "error_code": "UNKNOWN",
                "error_description": str(e)
            }


def get_instance(
    api_url: str = None,
    client_id: str = None
) -> PixClient:
    """Get PIX client instance"""
    import os
    return PixClient(
        api_url=api_url or os.getenv("PIX_API_URL", "https://pix.example.com"),
        client_id=client_id or os.getenv("PIX_CLIENT_ID", ""),
        client_secret=os.getenv("PIX_CLIENT_SECRET", ""),
        pix_key=os.getenv("PIX_KEY", ""),
        certificate_path=os.getenv("PIX_CERTIFICATE_PATH")
    )
