"""
UPI (Unified Payments Interface) Client
Production-grade connector for India's UPI payment system

Implements UPI APIs for:
- VPA (Virtual Payment Address) validation
- Collect requests
- Pay requests
- Transaction status
- Mandate management

Reference: https://www.npci.org.in/what-we-do/upi/product-overview
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


class UPITransactionType(Enum):
    """UPI transaction types"""
    PAY = "PAY"
    COLLECT = "COLLECT"
    MANDATE = "MANDATE"
    REFUND = "REFUND"


class UPITransactionStatus(Enum):
    """UPI transaction statuses"""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DEEMED = "DEEMED"
    EXPIRED = "EXPIRED"


class UPIResponseCode(Enum):
    """Common UPI response codes"""
    SUCCESS = "00"
    PENDING = "U30"
    INVALID_VPA = "U14"
    INSUFFICIENT_FUNDS = "U09"
    TRANSACTION_DECLINED = "U16"
    TIMEOUT = "U68"
    INVALID_AMOUNT = "U12"
    DUPLICATE_TRANSACTION = "U29"


@dataclass
class UPIAccount:
    """UPI account/VPA details"""
    vpa: str  # Virtual Payment Address (e.g., user@bank)
    name: Optional[str] = None
    ifsc: Optional[str] = None
    account_number: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"vpa": self.vpa}
        if self.name:
            result["name"] = self.name
        if self.ifsc:
            result["ifsc"] = self.ifsc
        if self.account_number:
            result["accountNumber"] = self.account_number
        return result


class UPIError(Exception):
    """UPI-specific error"""
    def __init__(self, response_code: str, description: str, txn_id: Optional[str] = None):
        self.response_code = response_code
        self.description = description
        self.txn_id = txn_id
        super().__init__(f"UPI Error {response_code}: {description}")


class UPIClient:
    """
    Production-grade UPI client
    
    Features:
    - VPA validation and lookup
    - Pay and Collect request handling
    - Transaction status tracking
    - Mandate (recurring payment) support
    - Idempotency and retry logic
    - Request signing
    """
    
    # API version
    API_VERSION = "2.0"
    
    # Timeouts
    DEFAULT_TIMEOUT = 30
    TRANSACTION_TIMEOUT = 60
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 1.0
    
    # Transaction limits (in INR)
    MAX_TRANSACTION_AMOUNT = 100000  # 1 lakh
    MAX_COLLECT_AMOUNT = 5000
    
    def __init__(
        self,
        psp_url: str,
        merchant_id: str,
        merchant_key: str,
        merchant_vpa: str,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize UPI client
        
        Args:
            psp_url: Payment Service Provider API URL
            merchant_id: Merchant/PSP ID
            merchant_key: API key for signing requests
            merchant_vpa: Merchant's VPA for receiving payments
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.psp_url = psp_url.rstrip('/')
        self.merchant_id = merchant_id
        self.merchant_key = merchant_key
        self.merchant_vpa = merchant_vpa
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"Initialized UPI client for merchant: {merchant_id}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _generate_checksum(self, data: Dict[str, Any]) -> str:
        """Generate checksum for request signing"""
        # Sort keys and create string
        sorted_data = sorted(data.items())
        data_string = "|".join(f"{k}={v}" for k, v in sorted_data)
        data_string += f"|{self.merchant_key}"
        
        # SHA256 hash
        checksum = hashlib.sha256(data_string.encode('utf-8')).hexdigest()
        return checksum
    
    def _generate_txn_id(self) -> str:
        """Generate unique transaction ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{self.merchant_id}{timestamp}{unique}"
    
    def _generate_headers(self) -> Dict[str, str]:
        """Generate API headers"""
        return {
            "Content-Type": "application/json",
            "X-Merchant-Id": self.merchant_id,
            "X-Api-Version": self.API_VERSION,
            "X-Request-Id": str(uuid.uuid4()),
            "X-Timestamp": datetime.now(timezone.utc).isoformat()
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
        url = f"{self.psp_url}{endpoint}"
        headers = self._generate_headers()
        
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        
        if data:
            data["checksum"] = self._generate_checksum(data)
        
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
                        result = json.loads(response_text) if response_text else {}
                        
                        # Check UPI response code
                        resp_code = result.get("responseCode", "00")
                        if resp_code != "00" and resp_code != "U30":  # Not success or pending
                            raise UPIError(
                                resp_code,
                                result.get("responseMessage", "Unknown error"),
                                result.get("txnId")
                            )
                        
                        return result
                    
                    # Handle HTTP errors
                    if response.status == 400:
                        error_data = json.loads(response_text) if response_text else {}
                        raise UPIError(
                            error_data.get("responseCode", "U99"),
                            error_data.get("responseMessage", "Bad request")
                        )
                    elif response.status >= 500:
                        last_error = UPIError("U68", "Server error")
                    else:
                        raise UPIError("U99", f"HTTP error: {response.status}")
                        
            except aiohttp.ClientError as e:
                last_error = UPIError("U68", f"Connection error: {str(e)}")
            except asyncio.TimeoutError:
                last_error = UPIError("U68", "Request timeout")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                wait_time = self.RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(f"UPI request failed, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        raise last_error or UPIError("U99", "Unknown error after retries")
    
    # ==================== VPA Operations ====================
    
    async def validate_vpa(self, vpa: str) -> Dict[str, Any]:
        """
        Validate a VPA (Virtual Payment Address)
        
        Args:
            vpa: VPA to validate (e.g., user@bank)
            
        Returns:
            VPA details including account holder name
        """
        logger.info(f"Validating VPA: {vpa}")
        
        data = {
            "merchantId": self.merchant_id,
            "vpa": vpa,
            "txnId": self._generate_txn_id()
        }
        
        result = await self._request_with_retry("POST", "/v1/vpa/validate", data)
        
        return {
            "success": True,
            "vpa": vpa,
            "name": result.get("payerName", result.get("name")),
            "valid": result.get("status") == "VALID",
            "bank": result.get("bankName")
        }
    
    async def lookup_vpa(self, vpa: str) -> Dict[str, Any]:
        """
        Look up VPA details
        
        Args:
            vpa: VPA to look up
            
        Returns:
            Account holder details
        """
        return await self.validate_vpa(vpa)
    
    # ==================== Payment Operations ====================
    
    async def initiate_pay(
        self,
        payer_vpa: str,
        amount: Decimal,
        note: str = "",
        ref_id: Optional[str] = None,
        ref_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate a PAY request (push payment)
        
        Args:
            payer_vpa: Payer's VPA
            amount: Amount in INR
            note: Transaction note/description
            ref_id: Reference ID for reconciliation
            ref_url: Reference URL for transaction details
            
        Returns:
            Transaction initiation result
        """
        if amount > self.MAX_TRANSACTION_AMOUNT:
            raise UPIError("U12", f"Amount exceeds limit of {self.MAX_TRANSACTION_AMOUNT}")
        
        txn_id = self._generate_txn_id()
        
        logger.info(f"Initiating PAY request: {txn_id} for {amount} INR")
        
        data = {
            "merchantId": self.merchant_id,
            "txnId": txn_id,
            "txnType": "PAY",
            "payerVpa": payer_vpa,
            "payeeVpa": self.merchant_vpa,
            "amount": str(amount),
            "currency": "INR",
            "note": note[:50] if note else "Payment",
            "refId": ref_id or txn_id,
            "refUrl": ref_url or ""
        }
        
        result = await self._request_with_retry(
            "POST", "/v1/pay/initiate", data,
            idempotency_key=txn_id
        )
        
        return {
            "success": True,
            "txn_id": txn_id,
            "upi_txn_id": result.get("upiTxnId"),
            "status": result.get("status", "PENDING"),
            "response_code": result.get("responseCode"),
            "payer_vpa": payer_vpa,
            "payee_vpa": self.merchant_vpa,
            "amount": float(amount),
            "currency": "INR"
        }
    
    async def initiate_collect(
        self,
        payer_vpa: str,
        amount: Decimal,
        note: str = "",
        expiry_minutes: int = 30,
        ref_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate a COLLECT request (pull payment)
        
        Args:
            payer_vpa: Payer's VPA to collect from
            amount: Amount in INR
            note: Transaction note
            expiry_minutes: Request expiry time
            ref_id: Reference ID
            
        Returns:
            Collect request result
        """
        if amount > self.MAX_COLLECT_AMOUNT:
            raise UPIError("U12", f"Collect amount exceeds limit of {self.MAX_COLLECT_AMOUNT}")
        
        txn_id = self._generate_txn_id()
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)).isoformat()
        
        logger.info(f"Initiating COLLECT request: {txn_id} for {amount} INR from {payer_vpa}")
        
        data = {
            "merchantId": self.merchant_id,
            "txnId": txn_id,
            "txnType": "COLLECT",
            "payerVpa": payer_vpa,
            "payeeVpa": self.merchant_vpa,
            "amount": str(amount),
            "currency": "INR",
            "note": note[:50] if note else "Payment request",
            "expiry": expiry,
            "refId": ref_id or txn_id
        }
        
        result = await self._request_with_retry(
            "POST", "/v1/collect/initiate", data,
            idempotency_key=txn_id
        )
        
        return {
            "success": True,
            "txn_id": txn_id,
            "upi_txn_id": result.get("upiTxnId"),
            "status": "PENDING",
            "payer_vpa": payer_vpa,
            "payee_vpa": self.merchant_vpa,
            "amount": float(amount),
            "currency": "INR",
            "expiry": expiry
        }
    
    async def check_status(self, txn_id: str) -> Dict[str, Any]:
        """
        Check transaction status
        
        Args:
            txn_id: Transaction ID to check
            
        Returns:
            Transaction status details
        """
        logger.info(f"Checking status for transaction: {txn_id}")
        
        data = {
            "merchantId": self.merchant_id,
            "txnId": txn_id
        }
        
        result = await self._request_with_retry("POST", "/v1/transaction/status", data)
        
        return {
            "success": True,
            "txn_id": txn_id,
            "upi_txn_id": result.get("upiTxnId"),
            "status": result.get("status"),
            "response_code": result.get("responseCode"),
            "response_message": result.get("responseMessage"),
            "amount": result.get("amount"),
            "payer_vpa": result.get("payerVpa"),
            "payee_vpa": result.get("payeeVpa"),
            "timestamp": result.get("timestamp")
        }
    
    # ==================== Refund Operations ====================
    
    async def initiate_refund(
        self,
        original_txn_id: str,
        amount: Optional[Decimal] = None,
        note: str = "Refund"
    ) -> Dict[str, Any]:
        """
        Initiate a refund for a completed transaction
        
        Args:
            original_txn_id: Original transaction ID to refund
            amount: Refund amount (full refund if not specified)
            note: Refund note
            
        Returns:
            Refund result
        """
        refund_txn_id = self._generate_txn_id()
        
        logger.info(f"Initiating refund for transaction: {original_txn_id}")
        
        data = {
            "merchantId": self.merchant_id,
            "txnId": refund_txn_id,
            "originalTxnId": original_txn_id,
            "txnType": "REFUND",
            "note": note[:50]
        }
        
        if amount:
            data["amount"] = str(amount)
        
        result = await self._request_with_retry(
            "POST", "/v1/refund/initiate", data,
            idempotency_key=refund_txn_id
        )
        
        return {
            "success": True,
            "refund_txn_id": refund_txn_id,
            "original_txn_id": original_txn_id,
            "status": result.get("status"),
            "amount": result.get("amount"),
            "response_code": result.get("responseCode")
        }
    
    # ==================== Mandate Operations ====================
    
    async def create_mandate(
        self,
        payer_vpa: str,
        amount: Decimal,
        frequency: str,  # DAILY, WEEKLY, FORTNIGHTLY, MONTHLY, BIMONTHLY, QUARTERLY, HALFYEARLY, YEARLY
        start_date: str,
        end_date: str,
        purpose: str = "Recurring payment"
    ) -> Dict[str, Any]:
        """
        Create a recurring payment mandate
        
        Args:
            payer_vpa: Payer's VPA
            amount: Maximum amount per debit
            frequency: Debit frequency
            start_date: Mandate start date (YYYY-MM-DD)
            end_date: Mandate end date (YYYY-MM-DD)
            purpose: Mandate purpose
            
        Returns:
            Mandate creation result
        """
        mandate_id = self._generate_txn_id()
        
        logger.info(f"Creating mandate: {mandate_id} for {payer_vpa}")
        
        data = {
            "merchantId": self.merchant_id,
            "mandateId": mandate_id,
            "payerVpa": payer_vpa,
            "payeeVpa": self.merchant_vpa,
            "amount": str(amount),
            "currency": "INR",
            "frequency": frequency,
            "startDate": start_date,
            "endDate": end_date,
            "purpose": purpose[:50]
        }
        
        result = await self._request_with_retry(
            "POST", "/v1/mandate/create", data,
            idempotency_key=mandate_id
        )
        
        return {
            "success": True,
            "mandate_id": mandate_id,
            "umn": result.get("umn"),  # Unique Mandate Number
            "status": result.get("status"),
            "payer_vpa": payer_vpa,
            "amount": float(amount),
            "frequency": frequency
        }
    
    # ==================== High-Level Operations ====================
    
    async def send_money(
        self,
        receiver_vpa: str,
        amount: Decimal,
        note: str = ""
    ) -> Dict[str, Any]:
        """
        High-level send money operation
        
        Args:
            receiver_vpa: Receiver's VPA
            amount: Amount in INR
            note: Transaction note
            
        Returns:
            Complete transfer result
        """
        txn_id = self._generate_txn_id()
        
        try:
            # Step 1: Validate receiver VPA
            logger.info(f"Step 1: Validating receiver VPA {receiver_vpa}")
            vpa_info = await self.validate_vpa(receiver_vpa)
            
            if not vpa_info.get("valid"):
                raise UPIError("U14", f"Invalid VPA: {receiver_vpa}")
            
            # Step 2: Initiate payment
            logger.info(f"Step 2: Initiating payment {txn_id}")
            pay_result = await self.initiate_pay(
                payer_vpa=self.merchant_vpa,
                amount=amount,
                note=note,
                ref_id=txn_id
            )
            
            # Step 3: Check status (for synchronous response)
            # In production, this would be handled via callback
            await asyncio.sleep(1)
            status = await self.check_status(pay_result["txn_id"])
            
            return {
                "success": status.get("status") == "SUCCESS",
                "txn_id": txn_id,
                "upi_txn_id": pay_result.get("upi_txn_id"),
                "receiver_vpa": receiver_vpa,
                "receiver_name": vpa_info.get("name"),
                "amount": float(amount),
                "currency": "INR",
                "status": status.get("status"),
                "response_code": status.get("response_code")
            }
            
        except UPIError as e:
            logger.error(f"UPI transfer failed: {e}")
            return {
                "success": False,
                "txn_id": txn_id,
                "error_code": e.response_code,
                "error_description": e.description
            }
        except Exception as e:
            logger.error(f"Unexpected error in send_money: {e}")
            return {
                "success": False,
                "txn_id": txn_id,
                "error_code": "U99",
                "error_description": str(e)
            }


def get_instance(
    psp_url: str = None,
    merchant_id: str = None
) -> UPIClient:
    """Get UPI client instance"""
    import os
    return UPIClient(
        psp_url=psp_url or os.getenv("UPI_PSP_URL", "https://upi.example.com"),
        merchant_id=merchant_id or os.getenv("UPI_MERCHANT_ID", "MERCHANT001"),
        merchant_key=os.getenv("UPI_MERCHANT_KEY", ""),
        merchant_vpa=os.getenv("UPI_MERCHANT_VPA", "merchant@bank")
    )
