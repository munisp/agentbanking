"""
CBN NIBSS (Nigeria Inter-Bank Settlement System) Integration Service
Connects Mojaloop with Nigeria's domestic payment infrastructure

NIBSS Products Supported:
- NIP (NIBSS Instant Payment) - Real-time interbank transfers
- NEFT (NIBSS Electronic Funds Transfer) - Batch transfers
- RTGS (Real-Time Gross Settlement) - High-value transfers
- BVN (Bank Verification Number) - Identity verification
- NIBSS Direct Debit - Recurring payments
"""

import asyncio
import logging
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
import aiohttp
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


class NIBSSProduct(Enum):
    """NIBSS payment products"""
    NIP = "NIP"  # NIBSS Instant Payment (real-time)
    NEFT = "NEFT"  # NIBSS Electronic Funds Transfer (batch)
    RTGS = "RTGS"  # Real-Time Gross Settlement (high-value)
    DIRECT_DEBIT = "DIRECT_DEBIT"  # Recurring payments


class NIBSSTransactionType(Enum):
    """NIBSS transaction types"""
    CREDIT = "C"  # Credit transfer
    DEBIT = "D"  # Debit transfer
    REVERSAL = "R"  # Reversal
    INQUIRY = "I"  # Balance inquiry


class NIBSSResponseCode(Enum):
    """NIBSS response codes"""
    SUCCESS = "00"
    PENDING = "09"
    INSUFFICIENT_FUNDS = "51"
    INVALID_ACCOUNT = "12"
    DUPLICATE_TRANSACTION = "94"
    TIMEOUT = "91"
    SYSTEM_ERROR = "96"


@dataclass
class NIBSSAccount:
    """NIBSS account details"""
    account_number: str
    bank_code: str  # CBN bank code (3 digits)
    account_name: str
    bvn: Optional[str] = None  # Bank Verification Number
    
    def validate(self) -> bool:
        """Validate account details"""
        if len(self.account_number) != 10:
            return False
        if len(self.bank_code) != 3:
            return False
        if self.bvn and len(self.bvn) != 11:
            return False
        return True


@dataclass
class NIPTransaction:
    """NIP (NIBSS Instant Payment) transaction"""
    transaction_id: str
    session_id: str
    source_account: NIBSSAccount
    destination_account: NIBSSAccount
    amount: float
    currency: str = "NGN"
    narration: str = ""
    payment_reference: str = ""
    transaction_type: NIBSSTransactionType = NIBSSTransactionType.CREDIT
    
    def to_nibss_format(self) -> Dict[str, Any]:
        """Convert to NIBSS NIP message format"""
        return {
            "SessionID": self.session_id,
            "ChannelCode": "7",  # 7 = Third-party integration
            "FromAccount": self.source_account.account_number,
            "FromBankCode": self.source_account.bank_code,
            "ToAccount": self.destination_account.account_number,
            "ToBankCode": self.destination_account.bank_code,
            "Amount": f"{self.amount:.2f}",
            "Currency": self.currency,
            "Narration": self.narration[:30],  # Max 30 chars
            "PaymentReference": self.payment_reference or self.transaction_id,
            "TransactionType": self.transaction_type.value,
            "BeneficiaryName": self.destination_account.account_name,
            "OriginatorName": self.source_account.account_name,
            "BeneficiaryBVN": self.destination_account.bvn or "",
            "OriginatorBVN": self.source_account.bvn or "",
        }


@dataclass
class RTGSTransaction:
    """RTGS (Real-Time Gross Settlement) transaction for high-value transfers"""
    transaction_id: str
    settlement_date: str  # YYYY-MM-DD
    source_account: NIBSSAccount
    destination_account: NIBSSAccount
    amount: float  # Minimum 10,000,000 NGN
    currency: str = "NGN"
    narration: str = ""
    
    def validate(self) -> bool:
        """Validate RTGS transaction"""
        # RTGS minimum amount is 10 million NGN
        if self.amount < 10_000_000:
            logger.error(f"RTGS amount {self.amount} below minimum 10,000,000 NGN")
            return False
        return True
    
    def to_nibss_format(self) -> Dict[str, Any]:
        """Convert to NIBSS RTGS message format"""
        return {
            "TransactionReference": self.transaction_id,
            "SettlementDate": self.settlement_date,
            "DebitAccount": self.source_account.account_number,
            "DebitBankCode": self.source_account.bank_code,
            "CreditAccount": self.destination_account.account_number,
            "CreditBankCode": self.destination_account.bank_code,
            "Amount": f"{self.amount:.2f}",
            "Currency": self.currency,
            "Narration": self.narration[:140],  # Max 140 chars for RTGS
            "BeneficiaryName": self.destination_account.account_name,
            "OriginatorName": self.source_account.account_name,
        }


class NIBSSClient:
    """Client for NIBSS API integration"""
    
    def __init__(
        self,
        base_url: str,
        institution_code: str,
        api_key: str,
        secret_key: str,
        timeout: int = 30
    ) -> None:
        self.base_url = base_url
        self.institution_code = institution_code
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC-SHA512 signature for request"""
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha512
        ).hexdigest()
        return signature
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"{self.institution_code}{timestamp}{unique_id}"
    
    async def name_enquiry(
        self,
        account_number: str,
        bank_code: str
    ) -> Dict[str, Any]:
        """
        Name Enquiry - Verify account details before transfer
        
        Args:
            account_number: 10-digit account number
            bank_code: 3-digit CBN bank code
            
        Returns:
            Account details including account name, BVN status
        """
        session_id = self._generate_session_id()
        
        payload = {
            "SessionID": session_id,
            "AccountNumber": account_number,
            "BankCode": bank_code,
            "ChannelCode": "7",
        }
        
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Signature": signature,
            "InstitutionCode": self.institution_code,
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/nip/name-enquiry",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                
                if result.get("ResponseCode") == NIBSSResponseCode.SUCCESS.value:
                    logger.info(f"Name enquiry successful: {account_number}")
                    return {
                        "success": True,
                        "account_number": account_number,
                        "account_name": result.get("AccountName"),
                        "bank_code": bank_code,
                        "bvn": result.get("BVN"),
                        "session_id": session_id,
                    }
                else:
                    logger.error(f"Name enquiry failed: {result.get('ResponseMessage')}")
                    return {
                        "success": False,
                        "error": result.get("ResponseMessage"),
                        "response_code": result.get("ResponseCode"),
                    }
        
        except Exception as e:
            logger.error(f"Name enquiry error: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def send_nip_transaction(
        self,
        transaction: NIPTransaction
    ) -> Dict[str, Any]:
        """
        Send NIP (NIBSS Instant Payment) transaction
        
        Args:
            transaction: NIP transaction details
            
        Returns:
            Transaction result with status and reference
        """
        payload = transaction.to_nibss_format()
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Signature": signature,
            "InstitutionCode": self.institution_code,
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/nip/fund-transfer",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                
                response_code = result.get("ResponseCode")
                
                if response_code == NIBSSResponseCode.SUCCESS.value:
                    logger.info(f"NIP transaction successful: {transaction.transaction_id}")
                    return {
                        "success": True,
                        "transaction_id": transaction.transaction_id,
                        "nibss_reference": result.get("SessionID"),
                        "response_code": response_code,
                        "response_message": result.get("ResponseMessage"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                elif response_code == NIBSSResponseCode.PENDING.value:
                    logger.warning(f"NIP transaction pending: {transaction.transaction_id}")
                    return {
                        "success": False,
                        "pending": True,
                        "transaction_id": transaction.transaction_id,
                        "response_code": response_code,
                        "response_message": result.get("ResponseMessage"),
                    }
                else:
                    logger.error(f"NIP transaction failed: {result.get('ResponseMessage')}")
                    return {
                        "success": False,
                        "transaction_id": transaction.transaction_id,
                        "error": result.get("ResponseMessage"),
                        "response_code": response_code,
                    }
        
        except Exception as e:
            logger.error(f"NIP transaction error: {e}")
            return {
                "success": False,
                "transaction_id": transaction.transaction_id,
                "error": str(e),
            }
    
    async def send_rtgs_transaction(
        self,
        transaction: RTGSTransaction
    ) -> Dict[str, Any]:
        """
        Send RTGS (Real-Time Gross Settlement) transaction
        
        Args:
            transaction: RTGS transaction details
            
        Returns:
            Transaction result with status and reference
        """
        if not transaction.validate():
            return {
                "success": False,
                "error": "Invalid RTGS transaction (minimum 10,000,000 NGN)",
            }
        
        payload = transaction.to_nibss_format()
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Signature": signature,
            "InstitutionCode": self.institution_code,
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/rtgs/fund-transfer",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                
                response_code = result.get("ResponseCode")
                
                if response_code == NIBSSResponseCode.SUCCESS.value:
                    logger.info(f"RTGS transaction successful: {transaction.transaction_id}")
                    return {
                        "success": True,
                        "transaction_id": transaction.transaction_id,
                        "rtgs_reference": result.get("TransactionReference"),
                        "settlement_date": transaction.settlement_date,
                        "response_code": response_code,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                else:
                    logger.error(f"RTGS transaction failed: {result.get('ResponseMessage')}")
                    return {
                        "success": False,
                        "transaction_id": transaction.transaction_id,
                        "error": result.get("ResponseMessage"),
                        "response_code": response_code,
                    }
        
        except Exception as e:
            logger.error(f"RTGS transaction error: {e}")
            return {
                "success": False,
                "transaction_id": transaction.transaction_id,
                "error": str(e),
            }
    
    async def query_transaction_status(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Query transaction status
        
        Args:
            session_id: NIBSS session ID
            
        Returns:
            Transaction status
        """
        payload = {
            "SessionID": session_id,
            "InstitutionCode": self.institution_code,
        }
        
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Signature": signature,
            "InstitutionCode": self.institution_code,
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/nip/transaction-status",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                
                return {
                    "session_id": session_id,
                    "status": result.get("TransactionStatus"),
                    "response_code": result.get("ResponseCode"),
                    "response_message": result.get("ResponseMessage"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
        
        except Exception as e:
            logger.error(f"Transaction status query error: {e}")
            return {
                "session_id": session_id,
                "error": str(e),
            }
    
    async def verify_bvn(
        self,
        bvn: str,
        account_number: str,
        bank_code: str
    ) -> Dict[str, Any]:
        """
        Verify BVN (Bank Verification Number) against account
        
        Args:
            bvn: 11-digit BVN
            account_number: 10-digit account number
            bank_code: 3-digit bank code
            
        Returns:
            BVN verification result
        """
        if len(bvn) != 11:
            return {
                "success": False,
                "error": "Invalid BVN length (must be 11 digits)",
            }
        
        payload = {
            "BVN": bvn,
            "AccountNumber": account_number,
            "BankCode": bank_code,
            "InstitutionCode": self.institution_code,
        }
        
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self._generate_signature(payload_str)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Signature": signature,
            "InstitutionCode": self.institution_code,
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/bvn/verify",
                json=payload,
                headers=headers
            ) as response:
                result = await response.json()
                
                if result.get("ResponseCode") == NIBSSResponseCode.SUCCESS.value:
                    return {
                        "success": True,
                        "bvn": bvn,
                        "account_number": account_number,
                        "verified": result.get("Verified", False),
                        "customer_name": result.get("CustomerName"),
                        "date_of_birth": result.get("DateOfBirth"),
                        "phone_number": result.get("PhoneNumber"),
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("ResponseMessage"),
                        "response_code": result.get("ResponseCode"),
                    }
        
        except Exception as e:
            logger.error(f"BVN verification error: {e}")
            return {
                "success": False,
                "error": str(e),
            }


class NIBSSBankDirectory:
    """NIBSS bank directory with CBN bank codes"""
    
    # Major Nigerian banks with CBN codes
    BANKS = {
        "044": {"name": "Access Bank", "nip_enabled": True, "rtgs_enabled": True},
        "063": {"name": "Diamond Bank (Access)", "nip_enabled": True, "rtgs_enabled": True},
        "050": {"name": "Ecobank Nigeria", "nip_enabled": True, "rtgs_enabled": True},
        "070": {"name": "Fidelity Bank", "nip_enabled": True, "rtgs_enabled": True},
        "011": {"name": "First Bank of Nigeria", "nip_enabled": True, "rtgs_enabled": True},
        "214": {"name": "First City Monument Bank", "nip_enabled": True, "rtgs_enabled": True},
        "058": {"name": "Guaranty Trust Bank", "nip_enabled": True, "rtgs_enabled": True},
        "030": {"name": "Heritage Bank", "nip_enabled": True, "rtgs_enabled": True},
        "301": {"name": "Jaiz Bank", "nip_enabled": True, "rtgs_enabled": False},
        "082": {"name": "Keystone Bank", "nip_enabled": True, "rtgs_enabled": True},
        "526": {"name": "Parallex Bank", "nip_enabled": True, "rtgs_enabled": False},
        "076": {"name": "Polaris Bank", "nip_enabled": True, "rtgs_enabled": True},
        "101": {"name": "Providus Bank", "nip_enabled": True, "rtgs_enabled": False},
        "221": {"name": "Stanbic IBTC Bank", "nip_enabled": True, "rtgs_enabled": True},
        "068": {"name": "Standard Chartered Bank", "nip_enabled": True, "rtgs_enabled": True},
        "232": {"name": "Sterling Bank", "nip_enabled": True, "rtgs_enabled": True},
        "100": {"name": "Suntrust Bank", "nip_enabled": True, "rtgs_enabled": False},
        "032": {"name": "Union Bank of Nigeria", "nip_enabled": True, "rtgs_enabled": True},
        "033": {"name": "United Bank for Africa", "nip_enabled": True, "rtgs_enabled": True},
        "215": {"name": "Unity Bank", "nip_enabled": True, "rtgs_enabled": True},
        "035": {"name": "Wema Bank", "nip_enabled": True, "rtgs_enabled": True},
        "057": {"name": "Zenith Bank", "nip_enabled": True, "rtgs_enabled": True},
    }
    
    @classmethod
    def get_bank_name(cls, bank_code: str) -> Optional[str]:
        """Get bank name from code"""
        bank = cls.BANKS.get(bank_code)
        return bank["name"] if bank else None
    
    @classmethod
    def is_nip_enabled(cls, bank_code: str) -> bool:
        """Check if bank supports NIP"""
        bank = cls.BANKS.get(bank_code)
        return bank["nip_enabled"] if bank else False
    
    @classmethod
    def is_rtgs_enabled(cls, bank_code: str) -> bool:
        """Check if bank supports RTGS"""
        bank = cls.BANKS.get(bank_code)
        return bank["rtgs_enabled"] if bank else False
    
    @classmethod
    def get_all_banks(cls) -> List[Dict[str, Any]]:
        """Get all banks"""
        return [
            {
                "code": code,
                "name": info["name"],
                "nip_enabled": info["nip_enabled"],
                "rtgs_enabled": info["rtgs_enabled"],
            }
            for code, info in cls.BANKS.items()
        ]


# Example usage
async def example_usage() -> None:
    """Example usage of NIBSS integration"""
    
    # Initialize NIBSS client
    async with NIBSSClient(
        base_url="https://api.nibss-plc.com.ng",
        institution_code="ABC",
        api_key="your-api-key",
        secret_key="your-secret-key"
    ) as nibss_client:
        
        # 1. Name Enquiry (verify account before transfer)
        name_enquiry = await nibss_client.name_enquiry(
            account_number="0123456789",
            bank_code="057"  # Zenith Bank
        )
        
        if name_enquiry["success"]:
            print(f"Account Name: {name_enquiry['account_name']}")
            
            # 2. Send NIP transaction
            source_account = NIBSSAccount(
                account_number="9876543210",
                bank_code="044",  # Access Bank
                account_name="John Doe",
                bvn="12345678901"
            )
            
            destination_account = NIBSSAccount(
                account_number="0123456789",
                bank_code="057",  # Zenith Bank
                account_name=name_enquiry["account_name"],
                bvn=name_enquiry.get("bvn")
            )
            
            nip_transaction = NIPTransaction(
                transaction_id=str(uuid.uuid4()),
                session_id=name_enquiry["session_id"],
                source_account=source_account,
                destination_account=destination_account,
                amount=50000.00,  # 50,000 NGN
                narration="Payment for services",
                payment_reference="INV-2025-001"
            )
            
            result = await nibss_client.send_nip_transaction(nip_transaction)
            
            if result["success"]:
                print(f"Transaction successful: {result['nibss_reference']}")
            else:
                print(f"Transaction failed: {result.get('error')}")
        
        # 3. Send RTGS transaction (high-value)
        rtgs_transaction = RTGSTransaction(
            transaction_id=str(uuid.uuid4()),
            settlement_date=datetime.utcnow().strftime("%Y-%m-%d"),
            source_account=source_account,
            destination_account=destination_account,
            amount=15_000_000.00,  # 15 million NGN
            narration="High-value corporate payment"
        )
        
        rtgs_result = await nibss_client.send_rtgs_transaction(rtgs_transaction)
        
        if rtgs_result["success"]:
            print(f"RTGS successful: {rtgs_result['rtgs_reference']}")


if __name__ == "__main__":
    asyncio.run(example_usage())

