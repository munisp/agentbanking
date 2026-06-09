"""
ACH Payment Gateway
Automated Clearing House for USA domestic transfers

Coverage: United States
Settlement: 1-2 business days (Standard), Same-day available
Fee: $0.25-1.00 per transaction
Use Case: Domestic USA transfers, payroll, bill payments
"""

import asyncio
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import httpx


class ACHTransactionType(Enum):
    """ACH transaction types"""
    PPD = "PPD"  # Prearranged Payment and Deposit (consumer)
    CCD = "CCD"  # Corporate Credit or Debit
    WEB = "WEB"  # Internet-initiated
    TEL = "TEL"  # Telephone-initiated
    CTX = "CTX"  # Corporate Trade Exchange


class ACHSpeed(Enum):
    """ACH processing speed"""
    STANDARD = "STANDARD"  # 1-2 business days
    SAME_DAY = "SAME_DAY"  # Same business day


class PaymentStatus(Enum):
    """Payment status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETURNED = "RETURNED"  # ACH return
    CANCELLED = "CANCELLED"


class ACHGateway:
    """
    ACH Payment Gateway
    
    Provides domestic USA transfers via ACH network
    
    Features:
    - NACHA file format
    - Routing number validation
    - Account validation
    - Same-day ACH support
    - Return handling
    - Batch processing
    """
    
    def __init__(
        self,
        api_url: str,
        routing_number: str,  # Our bank's routing number
        company_id: str,
        api_key: str,
        api_secret: str
    ):
        """
        Initialize ACH gateway
        
        Args:
            api_url: ACH API endpoint
            routing_number: Bank routing number (9 digits)
            company_id: Company identifier
            api_key: API key
            api_secret: API secret
        """
        self.api_url = api_url
        self.routing_number = routing_number
        self.company_id = company_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        # HTTP client
        self.client: Optional[httpx.AsyncClient] = None
        
        # Transaction tracking
        self._transactions: Dict[str, Dict] = {}
        
        # Batch tracking
        self._batches: Dict[str, List[str]] = {}
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=30)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def initiate_payment(
        self,
        transaction_id: str,
        sender_name: str,
        sender_routing_number: str,
        sender_account_number: str,
        recipient_name: str,
        recipient_routing_number: str,
        recipient_account_number: str,
        amount: Decimal,
        transaction_type: ACHTransactionType = ACHTransactionType.WEB,
        speed: ACHSpeed = ACHSpeed.STANDARD,
        description: str = "Transfer",
        addenda: Optional[str] = None
    ) -> Dict:
        """
        Initiate ACH payment
        
        Args:
            transaction_id: Unique transaction ID
            sender_name: Sender name
            sender_routing_number: Sender bank routing number (9 digits)
            sender_account_number: Sender account number
            recipient_name: Recipient name
            recipient_routing_number: Recipient bank routing number
            recipient_account_number: Recipient account number
            amount: Transfer amount (USD)
            transaction_type: ACH transaction type
            speed: Processing speed (standard or same-day)
            description: Transaction description
            addenda: Optional additional information
            
        Returns:
            Payment initiation response
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized. Use async context manager.")
        
        # Validate inputs
        self._validate_routing_number(sender_routing_number)
        self._validate_routing_number(recipient_routing_number)
        self._validate_account_number(sender_account_number)
        self._validate_account_number(recipient_account_number)
        
        # Check amount limits
        if amount > Decimal("1000000"):  # $1M limit for standard ACH
            return {
                "status": "REJECTED",
                "reason": "Amount exceeds ACH limit",
                "max_amount": "1000000"
            }
        
        # Same-day ACH has lower limit
        if speed == ACHSpeed.SAME_DAY and amount > Decimal("100000"):
            return {
                "status": "REJECTED",
                "reason": "Amount exceeds same-day ACH limit",
                "max_amount": "100000"
            }
        
        # Build NACHA entry
        nacha_entry = self._build_nacha_entry(
            transaction_id=transaction_id,
            sender_name=sender_name,
            sender_routing=sender_routing_number,
            sender_account=sender_account_number,
            recipient_name=recipient_name,
            recipient_routing=recipient_routing_number,
            recipient_account=recipient_account_number,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            addenda=addenda
        )
        
        # Generate signature
        signature = self._generate_signature(nacha_entry)
        
        # Determine processing date
        processing_date = self._calculate_processing_date(speed)
        
        # Send to ACH network
        try:
            response = await self.client.post(
                f"{self.api_url}/payments",
                json={
                    "entry": nacha_entry,
                    "signature": signature,
                    "speed": speed.value,
                    "processing_date": processing_date
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Company-ID": self.company_id
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Store transaction
            self._transactions[transaction_id] = {
                "transaction_id": transaction_id,
                "trace_number": data.get("trace_number"),
                "status": PaymentStatus.PENDING.value,
                "amount": float(amount),
                "recipient_routing": recipient_routing_number,
                "recipient_account": recipient_account_number,
                "speed": speed.value,
                "processing_date": processing_date,
                "initiated_at": datetime.now(timezone.utc).isoformat(),
                "estimated_completion": self._estimate_completion_time(speed)
            }
            
            return {
                "status": "SUCCESS",
                "transaction_id": transaction_id,
                "trace_number": data.get("trace_number"),
                "processing_date": processing_date,
                "estimated_completion": self._transactions[transaction_id]["estimated_completion"],
                "fee": self._calculate_fee(amount, speed)
            }
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.json() if e.response else {}
            return {
                "status": "FAILED",
                "error": error_detail.get("error", "Payment initiation failed"),
                "error_code": error_detail.get("code", "ACH_ERROR")
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e),
                "error_code": "NETWORK_ERROR"
            }
    
    async def get_payment_status(
        self,
        transaction_id: str,
        trace_number: Optional[str] = None
    ) -> Dict:
        """
        Get payment status
        
        Args:
            transaction_id: Transaction ID
            trace_number: ACH trace number
            
        Returns:
            Payment status information
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        # Check local cache
        if transaction_id in self._transactions:
            local_status = self._transactions[transaction_id]
            
            # If completed/failed/returned, return cached
            if local_status["status"] in ["COMPLETED", "FAILED", "RETURNED", "CANCELLED"]:
                return local_status
        
        # Query ACH network
        try:
            trace = trace_number or self._transactions.get(transaction_id, {}).get("trace_number")
            
            if not trace:
                return {
                    "status": "NOT_FOUND",
                    "error": "Transaction not found"
                }
            
            response = await self.client.get(
                f"{self.api_url}/payments/{trace}/status",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Company-ID": self.company_id
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Update local cache
            status = self._map_ach_status(data.get("status"))
            if transaction_id in self._transactions:
                self._transactions[transaction_id]["status"] = status
                if status == PaymentStatus.COMPLETED.value:
                    self._transactions[transaction_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                elif status == PaymentStatus.RETURNED.value:
                    self._transactions[transaction_id]["return_code"] = data.get("return_code")
                    self._transactions[transaction_id]["return_reason"] = data.get("return_reason")
            
            return {
                "transaction_id": transaction_id,
                "trace_number": trace,
                "status": status,
                "return_code": data.get("return_code"),
                "return_reason": data.get("return_reason"),
                "settlement_date": data.get("settlement_date"),
                "last_updated": data.get("last_updated")
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "status": "ERROR",
                "error": "Failed to retrieve status",
                "error_code": e.response.status_code
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
    
    async def create_batch(
        self,
        batch_id: str,
        transactions: List[Dict]
    ) -> Dict:
        """
        Create batch of ACH payments
        
        Args:
            batch_id: Unique batch ID
            transactions: List of transaction dictionaries
            
        Returns:
            Batch creation result
        """
        if not self.client:
            raise RuntimeError("Gateway not initialized")
        
        if len(transactions) > 10000:  # NACHA batch limit
            return {
                "status": "REJECTED",
                "reason": "Batch size exceeds limit",
                "max_size": 10000
            }
        
        # Process each transaction
        transaction_ids = []
        for txn in transactions:
            result = await self.initiate_payment(**txn)
            if result["status"] == "SUCCESS":
                transaction_ids.append(result["transaction_id"])
        
        # Store batch
        self._batches[batch_id] = transaction_ids
        
        return {
            "status": "SUCCESS",
            "batch_id": batch_id,
            "total_transactions": len(transactions),
            "successful": len(transaction_ids),
            "failed": len(transactions) - len(transaction_ids),
            "transaction_ids": transaction_ids
        }
    
    async def get_batch_status(self, batch_id: str) -> Dict:
        """Get batch status"""
        if batch_id not in self._batches:
            return {
                "status": "NOT_FOUND",
                "error": "Batch not found"
            }
        
        transaction_ids = self._batches[batch_id]
        
        # Get status for each transaction
        statuses = {}
        for txn_id in transaction_ids:
            if txn_id in self._transactions:
                status = self._transactions[txn_id]["status"]
                statuses[status] = statuses.get(status, 0) + 1
        
        return {
            "batch_id": batch_id,
            "total_transactions": len(transaction_ids),
            "status_breakdown": statuses,
            "completed": statuses.get(PaymentStatus.COMPLETED.value, 0),
            "pending": statuses.get(PaymentStatus.PENDING.value, 0) + statuses.get(PaymentStatus.PROCESSING.value, 0),
            "failed": statuses.get(PaymentStatus.FAILED.value, 0) + statuses.get(PaymentStatus.RETURNED.value, 0)
        }
    
    def _build_nacha_entry(
        self,
        transaction_id: str,
        sender_name: str,
        sender_routing: str,
        sender_account: str,
        recipient_name: str,
        recipient_routing: str,
        recipient_account: str,
        amount: Decimal,
        transaction_type: ACHTransactionType,
        description: str,
        addenda: Optional[str]
    ) -> Dict:
        """Build NACHA entry"""
        # Simplified NACHA format
        # In production, use proper NACHA library
        
        entry = {
            "record_type": "6",  # Entry detail record
            "transaction_code": "27",  # Checking account debit
            "receiving_dfi_id": recipient_routing[:8],
            "check_digit": recipient_routing[8],
            "dfi_account_number": recipient_account,
            "amount": int(amount * 100),  # Cents
            "individual_id": transaction_id,
            "individual_name": recipient_name[:22],
            "discretionary_data": "",
            "addenda_indicator": "1" if addenda else "0",
            "trace_number": f"{self.routing_number[:8]}{transaction_id[:7]}"
        }
        
        if addenda:
            entry["addenda"] = {
                "record_type": "7",
                "type_code": "05",
                "payment_related_info": addenda[:80]
            }
        
        return entry
    
    def _validate_routing_number(self, routing_number: str) -> bool:
        """Validate routing number with checksum"""
        if not routing_number or len(routing_number) != 9:
            raise ValueError(f"Invalid routing number length: {routing_number}")
        
        if not routing_number.isdigit():
            raise ValueError(f"Routing number must be numeric: {routing_number}")
        
        # ABA routing number checksum algorithm
        digits = [int(d) for d in routing_number]
        checksum = (
            3 * (digits[0] + digits[3] + digits[6]) +
            7 * (digits[1] + digits[4] + digits[7]) +
            1 * (digits[2] + digits[5] + digits[8])
        )
        
        if checksum % 10 != 0:
            raise ValueError(f"Invalid routing number checksum: {routing_number}")
        
        return True
    
    def _validate_account_number(self, account_number: str) -> bool:
        """Validate account number format"""
        if not account_number or len(account_number) > 17:
            raise ValueError(f"Invalid account number length: {account_number}")
        
        if not account_number.replace("-", "").isalnum():
            raise ValueError(f"Invalid account number format: {account_number}")
        
        return True
    
    def _generate_signature(self, entry: Dict) -> str:
        """Generate HMAC signature"""
        message = str(entry)
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _calculate_fee(self, amount: Decimal, speed: ACHSpeed) -> Decimal:
        """Calculate ACH fee"""
        if speed == ACHSpeed.SAME_DAY:
            return Decimal("1.00")  # $1.00 for same-day
        else:
            return Decimal("0.25")  # $0.25 for standard
    
    def _calculate_processing_date(self, speed: ACHSpeed) -> str:
        """Calculate processing date"""
        now = datetime.now(timezone.utc)
        
        if speed == ACHSpeed.SAME_DAY:
            # Same business day if before cutoff (2:45 PM ET)
            cutoff_hour = 14 + 5  # 2:45 PM ET in UTC (approximate)
            if now.hour < cutoff_hour and now.weekday() < 5:
                return now.date().isoformat()
            else:
                # Next business day
                next_day = now + timedelta(days=1)
                while next_day.weekday() >= 5:  # Skip weekends
                    next_day += timedelta(days=1)
                return next_day.date().isoformat()
        else:
            # Standard: 1-2 business days
            processing_date = now + timedelta(days=1)
            while processing_date.weekday() >= 5:
                processing_date += timedelta(days=1)
            return processing_date.date().isoformat()
    
    def _estimate_completion_time(self, speed: ACHSpeed) -> str:
        """Estimate completion time"""
        processing_date = datetime.fromisoformat(self._calculate_processing_date(speed))
        
        if speed == ACHSpeed.SAME_DAY:
            # Complete by end of business day
            completion = processing_date.replace(hour=17, minute=0, second=0)
        else:
            # Add 1 more business day for settlement
            completion = processing_date + timedelta(days=1)
            while completion.weekday() >= 5:
                completion += timedelta(days=1)
            completion = completion.replace(hour=9, minute=0, second=0)
        
        return completion.isoformat()
    
    def _map_ach_status(self, ach_status: str) -> str:
        """Map ACH status to internal status"""
        status_map = {
            "PENDING": PaymentStatus.PENDING.value,
            "PROCESSING": PaymentStatus.PROCESSING.value,
            "SETTLED": PaymentStatus.COMPLETED.value,
            "RETURNED": PaymentStatus.RETURNED.value,
            "FAILED": PaymentStatus.FAILED.value
        }
        
        return status_map.get(ach_status, PaymentStatus.PROCESSING.value)
