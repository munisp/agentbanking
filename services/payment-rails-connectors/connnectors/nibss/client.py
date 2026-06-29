"""
NIBSS (Nigeria Inter-Bank Settlement System) Payment Gateway Client
Production-ready implementation with comprehensive error handling
"""

import httpx
import hashlib
import hmac
import json
import time
import logging
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class NIBSSTransferType(Enum):
    """NIBSS transfer types"""
    NIP = "NIP"  # NIBSS Instant Payment
    RTGS = "RTGS"  # Real-Time Gross Settlement
    NEFT = "NEFT"  # National Electronic Funds Transfer

class NIBSSTransactionStatus(Enum):
    """NIBSS transaction status codes"""
    SUCCESS = "00"
    PENDING = "09"
    INSUFFICIENT_FUNDS = "51"
    INVALID_ACCOUNT = "25"
    SYSTEM_ERROR = "96"
    TIMEOUT = "91"
    DUPLICATE = "94"

class NIBSSError(Exception):
    """Base exception for NIBSS errors"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"NIBSS Error {code}: {message}")

class NIBSSClient:
    """
    NIBSS Payment Gateway Client
    Handles NIP (NIBSS Instant Payment) transactions
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        institution_code: str,
        base_url: str = "https://api.nibss-plc.com.ng",
        timeout: int = 30
    ):
        """
        Initialize NIBSS client
        
        Args:
            api_key: NIBSS API key
            secret_key: NIBSS secret key for signing requests
            institution_code: Bank/institution code
            base_url: NIBSS API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.institution_code = institution_code
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        self.client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
        
        logger.info(f"NIBSS client initialized for institution: {institution_code}")
    
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
    
    def _get_headers(self, signature: str) -> Dict[str, str]:
        """Get request headers with authentication"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Signature": signature,
            "X-Institution-Code": self.institution_code,
            "X-Request-Time": datetime.utcnow().isoformat()
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated request to NIBSS API
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            payload: Request payload
            
        Returns:
            Response data
            
        Raises:
            NIBSSError: On API errors
        """
        url = f"{self.base_url}{endpoint}"
        
        if payload:
            signature = self._generate_signature(payload)
        else:
            signature = ""
        
        headers = self._get_headers(signature)
        
        try:
            logger.info(f"NIBSS API request: {method} {endpoint}")
            
            if method.upper() == "POST":
                response = await self.client.post(url, json=payload, headers=headers)
            elif method.upper() == "GET":
                response = await self.client.get(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Log response
            logger.info(f"NIBSS API response: {response.status_code}")
            
            # Parse response
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise NIBSSError(
                    code="INVALID_RESPONSE",
                    message="Invalid JSON response from NIBSS",
                    details={"status_code": response.status_code, "body": response.text}
                )
            
            # Check for errors
            if response.status_code != 200:
                raise NIBSSError(
                    code=data.get("responseCode", "UNKNOWN"),
                    message=data.get("responseMessage", "Unknown error"),
                    details=data
                )
            
            # Check response code
            response_code = data.get("responseCode")
            if response_code != NIBSSTransactionStatus.SUCCESS.value:
                raise NIBSSError(
                    code=response_code,
                    message=data.get("responseMessage", "Transaction failed"),
                    details=data
                )
            
            return data
            
        except httpx.TimeoutException:
            logger.error(f"NIBSS API timeout: {endpoint}")
            raise NIBSSError(
                code="TIMEOUT",
                message="Request to NIBSS timed out",
                details={"endpoint": endpoint, "timeout": self.timeout}
            )
        except httpx.NetworkError as e:
            logger.error(f"NIBSS API network error: {str(e)}")
            raise NIBSSError(
                code="NETWORK_ERROR",
                message="Network error connecting to NIBSS",
                details={"error": str(e)}
            )
        except NIBSSError:
            raise
        except Exception as e:
            logger.error(f"NIBSS API unexpected error: {str(e)}")
            raise NIBSSError(
                code="UNKNOWN_ERROR",
                message="Unexpected error",
                details={"error": str(e)}
            )
    
    async def initiate_transfer(
        self,
        source_account: str,
        destination_account: str,
        destination_bank_code: str,
        amount: float,
        narration: str,
        beneficiary_name: str,
        reference: str,
        transfer_type: NIBSSTransferType = NIBSSTransferType.NIP
    ) -> Dict:
        """
        Initiate a NIBSS transfer
        
        Args:
            source_account: Source account number
            destination_account: Destination account number
            destination_bank_code: Destination bank code (3-digit)
            amount: Transfer amount in Naira
            narration: Transfer description
            beneficiary_name: Beneficiary account name
            reference: Unique transaction reference
            transfer_type: Type of transfer (NIP, RTGS, NEFT)
            
        Returns:
            Transfer response data
            
        Raises:
            NIBSSError: On transfer failure
        """
        payload = {
            "sourceAccountNumber": source_account,
            "destinationAccountNumber": destination_account,
            "destinationBankCode": destination_bank_code,
            "amount": f"{amount:.2f}",
            "narration": narration[:50],  # NIBSS limit
            "beneficiaryName": beneficiary_name,
            "transactionReference": reference,
            "transferType": transfer_type.value,
            "institutionCode": self.institution_code,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Initiating NIBSS transfer: {reference} - {amount} NGN")
        
        response = await self._make_request("POST", "/v1/transfers", payload)
        
        logger.info(f"NIBSS transfer initiated: {response.get('sessionId')}")
        
        return {
            "transaction_id": response.get("sessionId"),
            "reference": reference,
            "status": response.get("responseCode"),
            "message": response.get("responseMessage"),
            "amount": amount,
            "timestamp": response.get("timestamp"),
            "raw_response": response
        }
    
    async def get_transfer_status(self, session_id: str) -> Dict:
        """
        Query transfer status
        
        Args:
            session_id: NIBSS session ID
            
        Returns:
            Transfer status data
        """
        logger.info(f"Querying NIBSS transfer status: {session_id}")
        
        response = await self._make_request(
            "GET",
            f"/v1/transfers/{session_id}/status"
        )
        
        return {
            "session_id": session_id,
            "status": response.get("responseCode"),
            "message": response.get("responseMessage"),
            "completed_at": response.get("completedAt"),
            "raw_response": response
        }
    
    async def name_enquiry(
        self,
        account_number: str,
        bank_code: str
    ) -> Dict:
        """
        Perform name enquiry to validate account
        
        Args:
            account_number: Account number to validate
            bank_code: Bank code
            
        Returns:
            Account details
        """
        payload = {
            "accountNumber": account_number,
            "bankCode": bank_code,
            "institutionCode": self.institution_code
        }
        
        logger.info(f"NIBSS name enquiry: {account_number} at {bank_code}")
        
        response = await self._make_request("POST", "/v1/name-enquiry", payload)
        
        return {
            "account_number": account_number,
            "account_name": response.get("accountName"),
            "bank_code": bank_code,
            "bank_name": response.get("bankName"),
            "valid": True
        }
    
    async def get_bank_list(self) -> List[Dict]:
        """
        Get list of banks on NIBSS platform
        
        Returns:
            List of bank details
        """
        logger.info("Fetching NIBSS bank list")
        
        response = await self._make_request("GET", "/v1/banks")
        
        return response.get("banks", [])
    
    async def verify_transaction(self, reference: str) -> Dict:
        """
        Verify transaction by reference
        
        Args:
            reference: Transaction reference
            
        Returns:
            Transaction verification data
        """
        logger.info(f"Verifying NIBSS transaction: {reference}")
        
        response = await self._make_request(
            "GET",
            f"/v1/transactions/{reference}/verify"
        )
        
        return {
            "reference": reference,
            "status": response.get("responseCode"),
            "verified": response.get("responseCode") == NIBSSTransactionStatus.SUCCESS.value,
            "details": response
        }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("NIBSS client closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
