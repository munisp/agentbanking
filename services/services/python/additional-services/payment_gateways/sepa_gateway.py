"""
SEPA (Single Euro Payments Area) Gateway
ISO 20022 compliant instant payments for 36 European countries
"""

from typing import Dict, Optional, List
from decimal import Decimal
import httpx
import uuid
from datetime import datetime, timedelta
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class SEPAScheme(Enum):
    """SEPA payment schemes"""
    SCT = "SEPA Credit Transfer"  # Standard (1 day)
    INST = "SEPA Instant Credit Transfer"  # Instant (< 10s)


class SEPAStatus(Enum):
    """Payment status"""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class SEPAGateway:
    """
    SEPA Gateway for European instant payments
    
    Features:
    - IBAN-based transfers
    - ISO 20022 messaging
    - Instant payments (< 10s)
    - Standard payments (1 day)
    - Recall functionality
    - Strong customer authentication
    """
    
    def __init__(
        self,
        api_key: str,
        bic: str,
        iban: str,
        participant_name: str,
        base_url: str = "https://api.sepa-instant.eu",
        timeout: int = 30
    ):
        """
        Initialize SEPA gateway
        
        Args:
            api_key: API authentication key
            bic: Bank Identifier Code (SWIFT code)
            iban: International Bank Account Number
            participant_name: Legal name of participant
            base_url: SEPA API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.bic = bic
        self.iban = iban
        self.participant_name = participant_name
        self.base_url = base_url.rstrip('/')
        
        self.client = httpx.AsyncClient(timeout=timeout)
        
        # Fee structure
        self.fee_rate = Decimal("0.002")  # 0.2%
        self.min_fee = Decimal("0.10")  # €0.10
        self.max_fee = Decimal("10.00")  # €10.00
        
        # Limits
        self.max_amount = Decimal("999999")  # €999,999
        self.instant_max = Decimal("100000")  # €100,000 for instant
        
        logger.info(f"SEPA gateway initialized: BIC={bic}, IBAN={iban}")
    
    # ==================== Payment Initiation ====================
    
    async def initiate_payment(
        self,
        recipient_iban: str,
        recipient_name: str,
        recipient_bic: Optional[str],
        amount: Decimal,
        currency: str = "EUR",
        reference: str = "",
        instant: bool = True,
        end_to_end_id: Optional[str] = None
    ) -> Dict:
        """
        Initiate SEPA payment
        
        Args:
            recipient_iban: Recipient IBAN
            recipient_name: Recipient name
            recipient_bic: Recipient BIC (optional for SEPA zone)
            amount: Amount in EUR
            currency: Currency code (must be EUR)
            reference: Payment reference/memo
            instant: Use SEPA Instant vs standard
            end_to_end_id: End-to-end reference (generated if not provided)
        
        Returns:
            Payment result dictionary
        """
        # Validate inputs
        self._validate_payment(recipient_iban, amount, currency, instant)
        
        # Generate IDs
        msg_id = str(uuid.uuid4())
        pmt_inf_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        e2e_id = end_to_end_id or str(uuid.uuid4())
        
        # Calculate fee
        fee = self._calculate_fee(amount)
        
        # Build ISO 20022 pain.001 message
        payment_message = self._build_pain001_message(
            msg_id=msg_id,
            pmt_inf_id=pmt_inf_id,
            tx_id=tx_id,
            e2e_id=e2e_id,
            recipient_iban=recipient_iban,
            recipient_name=recipient_name,
            recipient_bic=recipient_bic,
            amount=amount,
            currency=currency,
            reference=reference,
            instant=instant
        )
        
        # Submit to SEPA network
        try:
            endpoint = "/instant/payments" if instant else "/standard/payments"
            response = await self._post(endpoint, payment_message)
            
            status = SEPAStatus.COMPLETED if instant else SEPAStatus.PENDING
            settlement_time = "< 10s" if instant else "1 business day"
            
            result = {
                "gateway": "SEPA",
                "transaction_id": tx_id,
                "message_id": msg_id,
                "end_to_end_id": e2e_id,
                "status": status.value,
                "amount": float(amount),
                "currency": currency,
                "fee": float(fee),
                "recipient_iban": recipient_iban,
                "recipient_name": recipient_name,
                "settlement_time": settlement_time,
                "scheme": SEPAScheme.INST.value if instant else SEPAScheme.SCT.value,
                "timestamp": datetime.utcnow().isoformat(),
                "reference": reference
            }
            
            logger.info(
                f"SEPA payment initiated: tx_id={tx_id}, "
                f"amount={amount} {currency}, instant={instant}"
            )
            
            return result
        
        except httpx.HTTPStatusError as e:
            logger.error(f"SEPA payment failed: {e.response.text}")
            return {
                "gateway": "SEPA",
                "transaction_id": tx_id,
                "status": SEPAStatus.REJECTED.value,
                "error": e.response.text,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"SEPA payment error: {e}")
            raise
    
    # ==================== Payment Status ====================
    
    async def get_payment_status(
        self,
        transaction_id: str
    ) -> Dict:
        """
        Get payment status
        
        Args:
            transaction_id: Transaction ID
        
        Returns:
            Payment status dictionary
        """
        try:
            response = await self._get(f"/payments/{transaction_id}")
            
            return {
                "transaction_id": transaction_id,
                "status": response["status"],
                "amount": response["amount"],
                "currency": response["currency"],
                "recipient_iban": response["creditorAccount"]["iban"],
                "timestamp": response["timestamp"],
                "settlement_date": response.get("settlementDate")
            }
        
        except Exception as e:
            logger.error(f"Failed to get payment status: {e}")
            raise
    
    # ==================== Payment Recall ====================
    
    async def recall_payment(
        self,
        transaction_id: str,
        reason: str
    ) -> Dict:
        """
        Recall SEPA Instant payment
        
        Args:
            transaction_id: Original transaction ID
            reason: Recall reason
        
        Returns:
            Recall result
        """
        recall_id = str(uuid.uuid4())
        
        recall_message = {
            "recallId": recall_id,
            "originalTransactionId": transaction_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            response = await self._post(
                f"/payments/{transaction_id}/recall",
                recall_message
            )
            
            logger.info(f"SEPA payment recall initiated: {recall_id}")
            
            return {
                "recall_id": recall_id,
                "transaction_id": transaction_id,
                "status": response["status"],
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"SEPA recall failed: {e}")
            raise
    
    # ==================== Bulk Payments ====================
    
    async def initiate_bulk_payment(
        self,
        payments: List[Dict],
        instant: bool = False
    ) -> Dict:
        """
        Initiate bulk SEPA payments
        
        Args:
            payments: List of payment dictionaries
            instant: Use SEPA Instant
        
        Returns:
            Bulk payment result
        """
        batch_id = str(uuid.uuid4())
        
        results = []
        total_amount = Decimal("0")
        
        for payment in payments:
            try:
                result = await self.initiate_payment(
                    recipient_iban=payment["iban"],
                    recipient_name=payment["name"],
                    recipient_bic=payment.get("bic"),
                    amount=Decimal(str(payment["amount"])),
                    reference=payment.get("reference", ""),
                    instant=instant
                )
                results.append(result)
                total_amount += Decimal(str(payment["amount"]))
            
            except Exception as e:
                logger.error(f"Bulk payment failed for {payment['iban']}: {e}")
                results.append({
                    "iban": payment["iban"],
                    "status": "FAILED",
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r.get("status") == "COMPLETED")
        
        logger.info(
            f"SEPA bulk payment: batch_id={batch_id}, "
            f"total={len(payments)}, successful={successful}"
        )
        
        return {
            "batch_id": batch_id,
            "total_payments": len(payments),
            "successful": successful,
            "failed": len(payments) - successful,
            "total_amount": float(total_amount),
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # ==================== Helper Methods ====================
    
    def _validate_payment(
        self,
        iban: str,
        amount: Decimal,
        currency: str,
        instant: bool
    ):
        """Validate payment parameters"""
        # Validate IBAN
        if not self._validate_iban(iban):
            raise ValueError(f"Invalid IBAN: {iban}")
        
        # Validate currency
        if currency != "EUR":
            raise ValueError(f"SEPA only supports EUR, got {currency}")
        
        # Validate amount
        if amount <= 0:
            raise ValueError(f"Amount must be positive: {amount}")
        
        if amount > self.max_amount:
            raise ValueError(
                f"Amount exceeds SEPA limit: {amount} > {self.max_amount}"
            )
        
        if instant and amount > self.instant_max:
            raise ValueError(
                f"Amount exceeds SEPA Instant limit: "
                f"{amount} > {self.instant_max}"
            )
    
    def _validate_iban(self, iban: str) -> bool:
        """
        Validate IBAN format and checksum
        
        Args:
            iban: IBAN to validate
        
        Returns:
            True if valid
        """
        # Remove spaces and convert to uppercase
        iban = iban.replace(" ", "").upper()
        
        # Check length (15-34 characters)
        if not 15 <= len(iban) <= 34:
            return False
        
        # Check format: 2 letters + 2 digits + up to 30 alphanumeric
        if not re.match(r'^[A-Z]{2}[0-9]{2}[A-Z0-9]+$', iban):
            return False
        
        # Validate checksum (mod 97)
        # Move first 4 characters to end
        rearranged = iban[4:] + iban[:4]
        
        # Replace letters with numbers (A=10, B=11, ..., Z=35)
        numeric = ""
        for char in rearranged:
            if char.isdigit():
                numeric += char
            else:
                numeric += str(ord(char) - ord('A') + 10)
        
        # Check if mod 97 == 1
        return int(numeric) % 97 == 1
    
    def _calculate_fee(self, amount: Decimal) -> Decimal:
        """Calculate transaction fee"""
        fee = amount * self.fee_rate
        
        # Apply min/max
        if fee < self.min_fee:
            fee = self.min_fee
        elif fee > self.max_fee:
            fee = self.max_fee
        
        return fee.quantize(Decimal("0.01"))
    
    def _build_pain001_message(
        self,
        msg_id: str,
        pmt_inf_id: str,
        tx_id: str,
        e2e_id: str,
        recipient_iban: str,
        recipient_name: str,
        recipient_bic: Optional[str],
        amount: Decimal,
        currency: str,
        reference: str,
        instant: bool
    ) -> Dict:
        """Build ISO 20022 pain.001 payment initiation message"""
        
        message = {
            "CstmrCdtTrfInitn": {
                "GrpHdr": {
                    "MsgId": msg_id,
                    "CreDtTm": datetime.utcnow().isoformat(),
                    "NbOfTxs": "1",
                    "CtrlSum": str(amount),
                    "InitgPty": {
                        "Nm": self.participant_name,
                        "Id": {
                            "OrgId": {
                                "BICOrBEI": self.bic
                            }
                        }
                    }
                },
                "PmtInf": {
                    "PmtInfId": pmt_inf_id,
                    "PmtMtd": "TRF",
                    "PmtTpInf": {
                        "SvcLvl": {
                            "Cd": "SEPA"
                        },
                        "LclInstrm": {
                            "Cd": "INST" if instant else "CORE"
                        }
                    },
                    "ReqdExctnDt": datetime.utcnow().date().isoformat(),
                    "Dbtr": {
                        "Nm": self.participant_name
                    },
                    "DbtrAcct": {
                        "Id": {
                            "IBAN": self.iban
                        }
                    },
                    "DbtrAgt": {
                        "FinInstnId": {
                            "BIC": self.bic
                        }
                    },
                    "CdtTrfTxInf": {
                        "PmtId": {
                            "InstrId": tx_id,
                            "EndToEndId": e2e_id
                        },
                        "Amt": {
                            "InstdAmt": {
                                "Ccy": currency,
                                "value": str(amount)
                            }
                        },
                        "CdtrAgt": {
                            "FinInstnId": {}
                        },
                        "Cdtr": {
                            "Nm": recipient_name
                        },
                        "CdtrAcct": {
                            "Id": {
                                "IBAN": recipient_iban
                            }
                        }
                    }
                }
            }
        }
        
        # Add BIC if provided
        if recipient_bic:
            message["CstmrCdtTrfInitn"]["PmtInf"]["CdtTrfTxInf"]["CdtrAgt"]["FinInstnId"]["BIC"] = recipient_bic
        
        # Add reference if provided
        if reference:
            message["CstmrCdtTrfInitn"]["PmtInf"]["CdtTrfTxInf"]["RmtInf"] = {
                "Ustrd": reference
            }
        
        return message
    
    async def _post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request to SEPA API"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = await self.client.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    async def _get(self, endpoint: str) -> Dict:
        """Make GET request to SEPA API"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# ==================== Singleton Instance ====================

_sepa_gateway: Optional[SEPAGateway] = None


def get_sepa_gateway() -> SEPAGateway:
    """Get singleton SEPA gateway instance"""
    global _sepa_gateway
    
    if _sepa_gateway is None:
        # In production, read from environment
        api_key = "..."  # Load from secure storage
        bic = "REMITTBIC"
        iban = "DE89370400440532013000"
        participant_name = "Remittance Platform Ltd"
        
        _sepa_gateway = SEPAGateway(
            api_key=api_key,
            bic=bic,
            iban=iban,
            participant_name=participant_name
        )
    
    return _sepa_gateway
