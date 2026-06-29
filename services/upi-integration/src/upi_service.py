"""
UPI (Unified Payments Interface) Integration Service
Connects India's instant payment system with Mojaloop hub
"""

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


class UPIIntegrationService:
    """
    UPI Integration Service for Mojaloop
    Implements NPCI UPI specifications for instant payments
    """
    
    def __init__(self, config: Dict[str, Any] = None) -> None:
        """Initialize UPI service"""
        self.config = config or {}
        self.npci_api_url = self.config.get('npci_api_url', 'https://api.npci.org.in/upi')
        self.merchant_id = self.config.get('merchant_id')
        self.merchant_key = self.config.get('merchant_key')
        self.vpa_suffix = self.config.get('vpa_suffix', '@paytm')  # Virtual Payment Address suffix
        
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
        """Generate UPI transaction ID (RRN - Retrieval Reference Number)"""
        timestamp = datetime.now().strftime('%y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4().int)[:6]
        return f"UPI{timestamp}{random_suffix}"
    
    def calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for UPI request"""
        # Sort keys and create string
        sorted_keys = sorted(data.keys())
        checksum_string = '|'.join([str(data[k]) for k in sorted_keys])
        
        # Add merchant key
        checksum_string += self.merchant_key
        
        # Calculate SHA-256 hash
        return hashlib.sha256(checksum_string.encode()).hexdigest()
    
    def create_payment_request(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create UPI payment request
        
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
        try:
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
            
            # Generate transaction ID
            transaction_id = self.generate_transaction_id()
            
            # Create UPI request
            upi_request = {
                'transaction_id': transaction_id,
                'payer_vpa': payment_data['payer_vpa'],
                'payee_vpa': payment_data['payee_vpa'],
                'amount': float(amount),
                'currency': 'INR',
                'note': payment_data.get('note', ''),
                'transaction_type': transaction_type.value,
                'merchant_id': self.merchant_id,
                'timestamp': datetime.now().isoformat(),
                'expiry': (datetime.now() + timedelta(minutes=5)).isoformat(),
                'status': UPIStatus.PENDING.value
            }
            
            # Calculate checksum
            upi_request['checksum'] = self.calculate_checksum(upi_request)
            
            logger.info(f"UPI payment request created: {transaction_id}")
            return {
                'status': 'success',
                'transaction_id': transaction_id,
                'upi_request': upi_request,
                'qr_code_data': self.generate_qr_code_data(upi_request)
            }
            
        except Exception as e:
            logger.error(f"Failed to create UPI payment request: {e}")
            raise
    
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
        Verify UPI payment status
        In production, this would call NPCI API
        """
        try:
            # Real NPCI verification API call
            logger.info(f"Verifying UPI transaction: {transaction_id}")
            
            import requests
            
            # NPCI API endpoint (use sandbox for testing, production for live)
            npci_url = os.getenv(
                'NPCI_API_URL',
                'https://api.npci.org.in/upi/v1/verify'
            )
            
            # Make API call to NPCI
            response = requests.post(
                npci_url,
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
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'transaction_id': transaction_id,
                    'status': data.get('status', UPIStatus.SUCCESS.value),
                    'verified_at': data.get('verifiedAt', datetime.now().isoformat()),
                    'settlement_date': data.get('settlementDate', datetime.now().date().isoformat()),
                    'npci_ref': data.get('npciReference')
                }
            else:
                # Fallback response if API fails
                logger.warning(f"NPCI API returned {response.status_code}, using fallback")
                return {
                    'transaction_id': transaction_id,
                    'status': UPIStatus.PENDING.value,
                    'verified_at': datetime.now().isoformat(),
                    'settlement_date': datetime.now().date().isoformat(),
                    'note': 'Verification pending - API unavailable'
                }
            
        except Exception as e:
            logger.error(f"Failed to verify UPI payment: {e}")
            raise
    
    def process_collect_request(self, collect_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process UPI collect request (pull payment)
        Payee requests money from payer
        """
        try:
            transaction_id = self.generate_transaction_id()
            
            collect_request = {
                'transaction_id': transaction_id,
                'payee_vpa': collect_data['payee_vpa'],
                'payer_vpa': collect_data['payer_vpa'],
                'amount': float(Decimal(str(collect_data['amount']))),
                'currency': 'INR',
                'note': collect_data.get('note', ''),
                'transaction_type': UPITransactionType.COLLECT.value,
                'expiry': (datetime.now() + timedelta(hours=24)).isoformat(),
                'status': 'PENDING_APPROVAL'
            }
            
            logger.info(f"UPI collect request created: {transaction_id}")
            return {
                'status': 'success',
                'transaction_id': transaction_id,
                'collect_request': collect_request,
                'message': 'Collect request sent to payer'
            }
            
        except Exception as e:
            logger.error(f"Failed to process collect request: {e}")
            raise
    
    def get_bank_details(self, vpa: str) -> Dict[str, Any]:
        """
        Get bank details from VPA
        In production, calls NPCI name resolution API
        """
        try:
            if not self.validate_vpa(vpa):
                raise ValueError(f"Invalid VPA: {vpa}")
            
            username, bank_code = vpa.split('@')
            
            # Real NPCI name resolution API call
            logger.info(f"Resolving VPA: {vpa}")
            
            import requests
            
            # NPCI name resolution endpoint
            npci_url = os.getenv(
                'NPCI_NAME_RESOLUTION_URL',
                'https://api.npci.org.in/upi/v1/resolve'
            )
            
            try:
                response = requests.post(
                    npci_url,
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
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'vpa': vpa,
                        'name': data.get('accountHolderName', 'Unknown'),
                        'bank_code': bank_code,
                        'bank_name': data.get('bankName', ''),
                        'verified': data.get('verified', True),
                        'npci_ref': data.get('reference')
                    }
                else:
                    logger.warning(f"NPCI name resolution failed: {response.status_code}")
            except Exception as api_error:
                logger.warning(f"NPCI API error: {api_error}")
            
            # Fallback response if API fails
            return {
                'vpa': vpa,
                'name': 'Account Holder',  # Generic fallback
                'bank_code': bank_code,
                'verified': False,
                'note': 'Name resolution unavailable - using fallback'
            }
            
        except Exception as e:
            logger.error(f"Failed to get bank details: {e}")
            raise
    
    def process_refund(self, refund_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process UPI refund"""
        try:
            original_txn_id = refund_data['original_transaction_id']
            refund_amount = Decimal(str(refund_data['amount']))
            
            refund_txn_id = self.generate_transaction_id()
            
            refund_request = {
                'refund_transaction_id': refund_txn_id,
                'original_transaction_id': original_txn_id,
                'amount': float(refund_amount),
                'currency': 'INR',
                'reason': refund_data.get('reason', 'Refund'),
                'timestamp': datetime.now().isoformat(),
                'status': 'PROCESSING'
            }
            
            logger.info(f"UPI refund initiated: {refund_txn_id} for original: {original_txn_id}")
            return {
                'status': 'success',
                'refund_transaction_id': refund_txn_id,
                'refund_request': refund_request
            }
            
        except Exception as e:
            logger.error(f"Failed to process refund: {e}")
            raise
    
    def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Get UPI transaction status"""
        try:
            # Real NPCI transaction status API call
            logger.info(f"Checking status for transaction: {transaction_id}")
            
            import requests
            
            # NPCI transaction status endpoint
            npci_url = os.getenv(
                'NPCI_STATUS_URL',
                'https://api.npci.org.in/upi/v1/status'
            )
            
            try:
                response = requests.post(
                    npci_url,
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
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'transaction_id': transaction_id,
                        'status': data.get('status', UPIStatus.PENDING.value),
                        'amount': data.get('amount', 0.0),
                        'currency': data.get('currency', 'INR'),
                        'timestamp': data.get('timestamp', datetime.now().isoformat()),
                        'settlement_status': data.get('settlementStatus', 'PENDING'),
                        'payer_vpa': data.get('payerVpa'),
                        'payee_vpa': data.get('payeeVpa'),
                        'npci_ref': data.get('npciReference')
                    }
                else:
                    logger.warning(f"NPCI status API failed: {response.status_code}")
            except Exception as api_error:
                logger.warning(f"NPCI API error: {api_error}")
            
            # Fallback response if API fails
            return {
                'transaction_id': transaction_id,
                'status': UPIStatus.PENDING.value,
                'amount': 0.0,
                'currency': 'INR',
                'timestamp': datetime.now().isoformat(),
                'settlement_status': 'UNKNOWN',
                'note': 'Status check unavailable - using fallback'
            }
            
        except Exception as e:
            logger.error(f"Failed to get transaction status: {e}")
            raise
    
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


# Example usage
if __name__ == '__main__':
    # Initialize UPI service
    config = {
        'npci_api_url': 'https://api.npci.org.in/upi',
        'merchant_id': 'MERCHANT123',
        'merchant_key': 'secret_key_here',
        'vpa_suffix': '@paytm'
    }
    
    upi_service = UPIIntegrationService(config)
    
    # Create payment request
    payment_data = {
        'payer_vpa': 'user123@paytm',
        'payee_vpa': 'merchant456@hdfcbank',
        'amount': Decimal('1000.00'),
        'currency': 'INR',
        'note': 'Payment for services',
        'transaction_type': UPITransactionType.P2M
    }
    
    result = upi_service.create_payment_request(payment_data)
    print(f"Payment request created: {result['transaction_id']}")
    print(f"QR Code: {result['qr_code_data']}")
    
    # Get supported banks
    banks = upi_service.get_supported_banks()
    print(f"Supported banks: {len(banks)}")
    
    # Get transaction limits
    limits = upi_service.get_transaction_limits()
    print(f"Transaction limits: {limits}")

