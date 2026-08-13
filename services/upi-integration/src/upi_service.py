"""
UPI (Unified Payments Interface) Integration Service
Connects India's instant payment system with Mojaloop hub
"""

import os
import uuid
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
from enum import Enum
import json

logger = logging.getLogger(__name__)


class UPITransactionType(Enum):
    """UPI transaction types"""
    P2P = "P2P"  # Person to Person
    P2M = "P2M"  # Person to Merchant
    P2A = "P2A"  # Person to Account
    COLLECT = "COLLECT"  # Collect request
    INTENT = "INTENT"  # Intent-based payment


class UPIStatus(Enum):
    """UPI transaction status"""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DEEMED = "DEEMED"  # Deemed success after timeout
    EXPIRED = "EXPIRED"


class UPIProviderError(Exception):
    """Raised when the NPCI/UPI provider cannot fulfil a request."""
    pass


class UPIProviderNotConfigured(UPIProviderError):
    """Raised when the NPCI provider endpoints/credentials are not configured."""
    pass


class UPIIntegrationService:
    """
    UPI Integration Service for Mojaloop
    Implements NPCI UPI specifications for instant payments
    """
    
    def __init__(self, config: Dict[str, Any] = None) -> None:
        """Initialize UPI service"""
        self.config = config or {}
        self.npci_api_url = self.config.get('npci_api_url') or os.getenv('NPCI_API_URL')
        self.merchant_id = self.config.get('merchant_id') or os.getenv('NPCI_MERCHANT_ID')
        self.merchant_key = self.config.get('merchant_key') or os.getenv('NPCI_MERCHANT_KEY')
        self.api_key = self.config.get('api_key') or os.getenv('NPCI_API_KEY')
        self.vpa_suffix = self.config.get('vpa_suffix', '@paytm')  # Virtual Payment Address suffix
        
        # Simulation-mode guard: a simulated UPI provider must never run in production.
        self.simulation_mode = os.getenv('UPI_SIMULATION_MODE', 'false').strip().lower() == 'true'
        environment = os.getenv('ENVIRONMENT', 'development').strip().lower()
        if self.simulation_mode and environment == 'production':
            raise RuntimeError(
                "UPI_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production. "
                "Refusing to start with a simulated UPI provider."
            )
        
        # Supported banks
        self.supported_banks = [
            'SBI', 'HDFC', 'ICICI', 'Axis', 'PNB', 'BOB', 'Canara',
            'Union', 'IDBI', 'Yes', 'Kotak', 'IndusInd', 'Federal'
        ]
        
        # Transaction limits (in INR)
        self.min_amount = Decimal('1.00')
        self.max_amount_p2p = Decimal('100000.00')  # 1 lakh
        self.max_amount_p2m = Decimal('200000.00')  # 2 lakhs
        
        logger.info("UPI Integration Service initialized")
    
    def _require_npci_configured(self) -> None:
        """Fail loud when the NPCI provider is not configured."""
        if not self.npci_api_url or not self.api_key or not self.merchant_id:
            raise UPIProviderNotConfigured(
                "NPCI UPI provider is not configured. Set NPCI_API_URL, NPCI_API_KEY "
                "and NPCI_MERCHANT_ID (or pass them via the service config). "
                "Refusing to fabricate a UPI response."
            )
    
    def validate_vpa(self, vpa: str) -> bool:
        """
        Validate Virtual Payment Address (VPA)
        Format: username@bankname
        """
        if not vpa or '@' not in vpa:
            return False
        
        parts = vpa.split('@')
        if len(parts) != 2:
            return False
        
        username, bank = parts
        
        # Username validation
        if not username or len(username) < 3 or len(username) > 50:
            return False
        
        # Bank validation
        if not bank or len(bank) < 2:
            return False
        
        return True
    
    def generate_transaction_id(self) -> str:
        """Generate a local UPI transaction reference (NOT a provider RRN)."""
        timestamp = datetime.now().strftime('%y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4().int)[:6]
        return f"UPI{timestamp}{random_suffix}"
    
    def calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for UPI request"""
        if not self.merchant_key:
            raise UPIProviderNotConfigured("NPCI merchant key is not configured; cannot sign request.")
        # Sort keys and create string
        sorted_keys = sorted(data.keys())
        checksum_string = '|'.join([str(data[k]) for k in sorted_keys])
        
        # Add merchant key
        checksum_string += self.merchant_key
        
        # Calculate SHA-256 hash
        return hashlib.sha256(checksum_string.encode()).hexdigest()
    
    def create_payment_request(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create UPI payment request.
        
        Performs local validation, then requires a configured NPCI provider to
        submit the payment. If no real provider is configured, this fails loud
        instead of fabricating a successful transaction/RRN.
        
        Args:
            payment_data: {
                'payer_vpa': str,
                'payee_vpa': str,
                'amount': Decimal,
                'currency': str (must be INR),
                'note': str,
                'transaction_type': UPITransactionType
            }
        """
        # Validate VPAs
        if not self.validate_vpa(payment_data['payer_vpa']):
            raise ValueError(f"Invalid payer VPA: {payment_data['payer_vpa']}")
        
        if not self.validate_vpa(payment_data['payee_vpa']):
            raise ValueError(f"Invalid payee VPA: {payment_data['payee_vpa']}")
        
        # Validate currency
        if payment_data.get('currency') != 'INR':
            raise ValueError("UPI only supports INR currency")
        
        # Validate amount
        amount = Decimal(str(payment_data['amount']))
        if amount < self.min_amount:
            raise ValueError(f"Amount below minimum: {self.min_amount} INR")
        
        transaction_type = payment_data.get('transaction_type', UPITransactionType.P2P)
        max_amount = self.max_amount_p2m if transaction_type == UPITransactionType.P2M else self.max_amount_p2p
        
        if amount > max_amount:
            raise ValueError(f"Amount exceeds maximum: {max_amount} INR")
        
        # Never fabricate a success/RRN: require the real NPCI provider.
        self._require_npci_configured()
        raise UPIProviderError(
            "NPCI payment submission requires a certified PSP/bank integration "
            "that is not implemented in this service. Refusing to fabricate a "
            "UPI transaction id or success status."
        )
    
    def generate_qr_code_data(self, upi_request: Dict[str, Any]) -> str:
        """
        Generate UPI QR code data string
        Format: upi://pay?pa=<payee_vpa>&pn=<payee_name>&am=<amount>&tn=<note>&tr=<transaction_id>
        """
        qr_data = (
            f"upi://pay?"
            f"pa={upi_request['payee_vpa']}&"
            f"am={upi_request['amount']}&"
            f"tn={upi_request.get('note', '')}&"
            f"tr={upi_request['transaction_id']}&"
            f"cu={upi_request['currency']}"
        )
        return qr_data
    
    def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verify UPI payment status via the NPCI verification API.

        Fails loud on any provider failure: never synthesizes a status.
        """
        logger.info(f"Verifying UPI transaction: {transaction_id}")
        
        verify_url = self.config.get('npci_verify_url') or os.getenv('NPCI_VERIFY_URL')
        if not verify_url or not self.api_key:
            raise UPIProviderNotConfigured(
                "NPCI verification is not configured. Set NPCI_VERIFY_URL and NPCI_API_KEY."
            )
        
        import requests
        try:
            response = requests.post(
                verify_url,
                json={
                    'transactionId': transaction_id,
                    'merchantId': self.merchant_id
                },
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
        except requests.RequestException as e:
            raise UPIProviderError(f"NPCI verification request failed: {e}")
        
        if response.status_code == 404:
            raise UPIProviderError(f"NPCI reports transaction '{transaction_id}' not found (HTTP 404).")
        if response.status_code != 200:
            raise UPIProviderError(f"NPCI verification failed with HTTP {response.status_code}.")
        
        data = response.json()
        status = data.get('status')
        if not status:
            raise UPIProviderError("NPCI verification response did not include a status.")
        
        return {
            'transaction_id': transaction_id,
            'status': status,
            'verified_at': data.get('verifiedAt', datetime.now().isoformat()),
            'settlement_date': data.get('settlementDate'),
            'npci_ref': data.get('npciReference')
        }
    
    def process_collect_request(self, collect_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process UPI collect request (pull payment).
        Payee requests money from payer.

        Requires a configured NPCI provider; fails loud otherwise instead of
        fabricating a collect request that was never sent to the payer's PSP.
        """
        if not self.validate_vpa(collect_data.get('payee_vpa', '')):
            raise ValueError(f"Invalid payee VPA: {collect_data.get('payee_vpa')}")
        if not self.validate_vpa(collect_data.get('payer_vpa', '')):
            raise ValueError(f"Invalid payer VPA: {collect_data.get('payer_vpa')}")
        
        self._require_npci_configured()
        raise UPIProviderError(
            "NPCI collect-request submission requires a certified PSP/bank integration "
            "that is not implemented in this service. Refusing to fabricate a collect "
            "request confirmation."
        )
    
    def get_bank_details(self, vpa: str) -> Dict[str, Any]:
        """
        Get bank details from VPA via the NPCI name resolution API.

        Fails loud on any provider failure: never returns a fabricated name.
        """
        if not self.validate_vpa(vpa):
            raise ValueError(f"Invalid VPA: {vpa}")
        
        username, bank_code = vpa.split('@')
        
        logger.info(f"Resolving VPA: {vpa}")
        
        resolve_url = self.config.get('npci_resolve_url') or os.getenv('NPCI_NAME_RESOLUTION_URL')
        if not resolve_url or not self.api_key:
            raise UPIProviderNotConfigured(
                "NPCI name resolution is not configured. Set NPCI_NAME_RESOLUTION_URL and NPCI_API_KEY."
            )
        
        import requests
        try:
            response = requests.post(
                resolve_url,
                json={
                    'vpa': vpa,
                    'merchantId': self.merchant_id
                },
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
        except requests.RequestException as e:
            raise UPIProviderError(f"NPCI name resolution request failed: {e}")
        
        if response.status_code == 404:
            raise UPIProviderError(f"NPCI could not resolve VPA '{vpa}' (HTTP 404).")
        if response.status_code != 200:
            raise UPIProviderError(f"NPCI name resolution failed with HTTP {response.status_code}.")
        
        data = response.json()
        return {
            'vpa': vpa,
            'name': data.get('accountHolderName'),
            'bank_code': bank_code,
            'bank_name': data.get('bankName'),
            'verified': bool(data.get('verified', False)),
            'npci_ref': data.get('reference')
        }
    
    def process_refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process UPI refund.

        Requires a configured NPCI provider; fails loud otherwise instead of
        fabricating a refund transaction id.
        """
        if not refund_data.get('original_transaction_id'):
            raise ValueError("original_transaction_id is required for a refund")
        refund_amount = Decimal(str(refund_data['amount']))
        if refund_amount < self.min_amount:
            raise ValueError(f"Refund amount below minimum: {self.min_amount} INR")
        
        self._require_npci_configured()
        raise UPIProviderError(
            "NPCI refund submission requires a certified PSP/bank integration "
            "that is not implemented in this service. Refusing to fabricate a "
            "refund transaction id or status."
        )
    
    def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get UPI transaction status via the NPCI status API.

        Fails loud on any provider failure: never synthesizes a status.
        """
        logger.info(f"Checking status for transaction: {transaction_id}")
        
        status_url = self.config.get('npci_status_url') or os.getenv('NPCI_STATUS_URL')
        if not status_url or not self.api_key:
            raise UPIProviderNotConfigured(
                "NPCI status check is not configured. Set NPCI_STATUS_URL and NPCI_API_KEY."
            )
        
        import requests
        try:
            response = requests.post(
                status_url,
                json={
                    'transactionId': transaction_id,
                    'merchantId': self.merchant_id
                },
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
        except requests.RequestException as e:
            raise UPIProviderError(f"NPCI status request failed: {e}")
        
        if response.status_code == 404:
            raise UPIProviderError(f"NPCI reports transaction '{transaction_id}' not found (HTTP 404).")
        if response.status_code != 200:
            raise UPIProviderError(f"NPCI status check failed with HTTP {response.status_code}.")
        
        data = response.json()
        status = data.get('status')
        if not status:
            raise UPIProviderError("NPCI status response did not include a status.")
        
        return {
            'transaction_id': transaction_id,
            'status': status,
            'amount': data.get('amount'),
            'currency': data.get('currency', 'INR'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'settlement_status': data.get('settlementStatus'),
            'payer_vpa': data.get('payerVpa'),
            'payee_vpa': data.get('payeeVpa'),
            'npci_ref': data.get('npciReference')
        }
    
    def create_mojaloop_quote(self, upi_payment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create Mojaloop quote from UPI payment
        Bridge between UPI and Mojaloop
        """
        try:
            quote_id = str(uuid.uuid4())
            
            # Convert UPI VPA to Mojaloop participant
            payer_fsp = self._vpa_to_participant(upi_payment['payer_vpa'])
            payee_fsp = self._vpa_to_participant(upi_payment['payee_vpa'])
            
            mojaloop_quote = {
                'quote_id': quote_id,
                'transaction_id': upi_payment['transaction_id'],
                'payer_fsp': payer_fsp,
                'payee_fsp': payee_fsp,
                'amount': upi_payment['amount'],
                'currency': 'INR',
                'fees': 0.0,  # UPI has no fees for P2P
                'total_amount': upi_payment['amount'],
                'payment_system': 'UPI',
                'payment_system_reference': upi_payment['transaction_id']
            }
            
            logger.info(f"Mojaloop quote created from UPI payment: {quote_id}")
            return mojaloop_quote
            
        except Exception as e:
            logger.error(f"Failed to create Mojaloop quote: {e}")
            raise
    
    def _vpa_to_participant(self, vpa: str) -> str:
        """Convert VPA to Mojaloop participant ID"""
        # Extract bank code from VPA
        _, bank_code = vpa.split('@')
        return f"upi-{bank_code}"
    
    def get_supported_banks(self) -> List[Dict[str, Any]]:
        """Get list of supported UPI banks"""
        return [
            {'code': 'SBI', 'name': 'State Bank of India', 'upi_handle': '@sbi'},
            {'code': 'HDFC', 'name': 'HDFC Bank', 'upi_handle': '@hdfcbank'},
            {'code': 'ICICI', 'name': 'ICICI Bank', 'upi_handle': '@icici'},
            {'code': 'Axis', 'name': 'Axis Bank', 'upi_handle': '@axisbank'},
            {'code': 'PNB', 'name': 'Punjab National Bank', 'upi_handle': '@pnb'},
            {'code': 'BOB', 'name': 'Bank of Baroda', 'upi_handle': '@bob'},
            {'code': 'Canara', 'name': 'Canara Bank', 'upi_handle': '@canara'},
            {'code': 'Paytm', 'name': 'Paytm Payments Bank', 'upi_handle': '@paytm'},
            {'code': 'PhonePe', 'name': 'PhonePe', 'upi_handle': '@ybl'},
            {'code': 'GooglePay', 'name': 'Google Pay', 'upi_handle': '@okaxis'},
        ]
    
    def get_transaction_limits(self) -> Dict[str, Any]:
        """Get UPI transaction limits"""
        return {
            'min_amount': float(self.min_amount),
            'max_amount_p2p': float(self.max_amount_p2p),
            'max_amount_p2m': float(self.max_amount_p2m),
            'currency': 'INR',
            'daily_limit': 100000.00,  # 1 lakh per day
            'monthly_limit': 1000000.00  # 10 lakhs per month
        }


if __name__ == '__main__':
    # Local smoke run: list static reference data only.
    # Payment creation/verification requires a configured NPCI provider and
    # fails loud when one is not present.
    upi_service = UPIIntegrationService()
    print(f"Supported banks: {len(upi_service.get_supported_banks())}")
    print(f"Transaction limits: {upi_service.get_transaction_limits()}")
    try:
        upi_service.create_payment_request({
            'payer_vpa': 'user123@paytm',
            'payee_vpa': 'merchant456@hdfcbank',
            'amount': Decimal('1000.00'),
            'currency': 'INR',
            'note': 'Payment for services',
            'transaction_type': UPITransactionType.P2M,
        })
    except UPIProviderError as e:
        print(f"Payment request correctly refused without provider: {e}")
