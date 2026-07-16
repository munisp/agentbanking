#!/usr/bin/env python3
"""
FPS (Faster Payments Service) Integration - UK
Real-time payment system for GBP transfers
"""

from typing import Dict, Optional
from datetime import datetime
from decimal import Decimal
import logging
import uuid
import re

logger = logging.getLogger(__name__)


class FPSConnector:
    """
    Connector for UK Faster Payments Service (FPS)
    
    FPS enables near-instant GBP transfers between UK bank accounts
    Available 24/7/365
    """
    
    # FPS transaction limits
    MAX_TRANSACTION_AMOUNT = Decimal("1000000.00")  # £1M per transaction
    MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    
    # Sort code validation pattern
    SORT_CODE_PATTERN = re.compile(r'^\d{6}$')
    
    # Account number validation pattern
    ACCOUNT_NUMBER_PATTERN = re.compile(r'^\d{8}$')
    
    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        Initialize FPS connector
        
        Args:
            config: Configuration including API credentials
        """
        self.config = config or {}
        self.api_url = self.config.get("api_url", "https://api.fps.uk/v1")
        self.api_key = self.config.get("api_key")
        self.participant_id = self.config.get("participant_id")
        
        # In production, validate credentials
        if not self.api_key or not self.participant_id:
            logger.warning("FPS credentials not configured")
    
    def validate_account(
        self,
        sort_code: str,
        account_number: str,
        account_name: Optional[str] = None
    ) -> Dict:
        """
        Validate UK bank account details
        
        Args:
            sort_code: 6-digit sort code (e.g., "123456")
            account_number: 8-digit account number
            account_name: Account holder name (optional)
            
        Returns:
            Validation result
        """
        errors = []
        
        # Validate sort code format
        if not self.SORT_CODE_PATTERN.match(sort_code):
            errors.append("Sort code must be 6 digits")
        
        # Validate account number format
        if not self.ACCOUNT_NUMBER_PATTERN.match(account_number):
            errors.append("Account number must be 8 digits")
        
        if errors:
            return {
                "valid": False,
                "errors": errors
            }
        
        # In production, call FPS CoP (Confirmation of Payee) API
        # to verify account name matches
        
        return {
            "valid": True,
            "sort_code": sort_code,
            "account_number": account_number,
            "account_name": account_name,
            "bank_name": self._get_bank_name(sort_code),
            "verified_at": datetime.utcnow().isoformat()
        }
    
    def initiate_payment(
        self,
        amount: Decimal,
        sender_sort_code: str,
        sender_account_number: str,
        sender_name: str,
        beneficiary_sort_code: str,
        beneficiary_account_number: str,
        beneficiary_name: str,
        reference: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Initiate FPS payment
        
        Args:
            amount: Payment amount in GBP
            sender_sort_code: Sender's sort code
            sender_account_number: Sender's account number
            sender_name: Sender's name
            beneficiary_sort_code: Beneficiary's sort code
            beneficiary_account_number: Beneficiary's account number
            beneficiary_name: Beneficiary's name
            reference: Payment reference (max 18 chars)
            metadata: Additional metadata
            
        Returns:
            Payment initiation result
        """
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            return {
                "success": False,
                "error": f"Amount must be at least £{self.MIN_TRANSACTION_AMOUNT}"
            }
        
        if amount > self.MAX_TRANSACTION_AMOUNT:
            return {
                "success": False,
                "error": f"Amount exceeds maximum of £{self.MAX_TRANSACTION_AMOUNT}"
            }
        
        # Validate sender account
        sender_validation = self.validate_account(sender_sort_code, sender_account_number, sender_name)
        if not sender_validation["valid"]:
            return {
                "success": False,
                "error": "Invalid sender account",
                "details": sender_validation["errors"]
            }
        
        # Validate beneficiary account
        beneficiary_validation = self.validate_account(
            beneficiary_sort_code,
            beneficiary_account_number,
            beneficiary_name
        )
        if not beneficiary_validation["valid"]:
            return {
                "success": False,
                "error": "Invalid beneficiary account",
                "details": beneficiary_validation["errors"]
            }
        
        # Generate payment ID
        payment_id = f"fps_{uuid.uuid4().hex[:16]}"
        
        # Truncate reference to 18 characters (FPS limit)
        if reference and len(reference) > 18:
            reference = reference[:18]
        
        # Create payment request
        payment_request = {
            "payment_id": payment_id,
            "amount": float(amount),
            "currency": "GBP",
            "sender": {
                "sort_code": sender_sort_code,
                "account_number": sender_account_number,
                "name": sender_name,
                "bank": sender_validation.get("bank_name")
            },
            "beneficiary": {
                "sort_code": beneficiary_sort_code,
                "account_number": beneficiary_account_number,
                "name": beneficiary_name,
                "bank": beneficiary_validation.get("bank_name")
            },
            "reference": reference or f"Payment {payment_id[:8]}",
            "metadata": metadata or {},
            "initiated_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "estimated_completion": self._estimate_completion_time()
        }
        
        # In production, call FPS API to submit payment
        # response = self._call_fps_api("/payments", payment_request)
        
        # Simulate success
        payment_request["status"] = "processing"
        payment_request["fps_transaction_id"] = f"FPS{uuid.uuid4().hex[:12].upper()}"
        
        logger.info(f"FPS payment initiated: {payment_id}")
        
        return {
            "success": True,
            "payment": payment_request
        }
    
    def get_payment_status(self, payment_id: str) -> Dict:
        """
        Get payment status
        
        Args:
            payment_id: Payment identifier
            
        Returns:
            Payment status
        """
        # In production, call FPS API
        # response = self._call_fps_api(f"/payments/{payment_id}")
        
        # Simulate status
        return {
            "payment_id": payment_id,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "settlement_date": datetime.utcnow().date().isoformat()
        }
    
    def _get_bank_name(self, sort_code: str) -> str:
        """
        Get bank name from sort code
        
        In production, use official sort code directory
        """
        # Simplified mapping (first 2 digits)
        bank_mapping = {
            "01": "Lloyds Bank",
            "20": "Barclays",
            "30": "Lloyds Bank",
            "40": "HSBC",
            "60": "National Westminster Bank",
            "77": "Lloyds Bank",
            "80": "Bank of Scotland",
            "83": "Clydesdale Bank",
        }
        
        prefix = sort_code[:2]
        return bank_mapping.get(prefix, "Unknown Bank")
    
    def _estimate_completion_time(self) -> str:
        """Estimate payment completion time"""
        # FPS typically completes within seconds
        return "Within 2 hours"
    
    def _call_fps_api(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Call FPS API (placeholder)
        
        In production, implement actual API calls with:
        - Authentication (API key, mTLS)
        - Request signing
        - Error handling
        - Retry logic
        """
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Participant-ID": self.participant_id,
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_url}{endpoint}"
        
        # This is a placeholder - actual implementation needed
        logger.info(f"FPS API call: {endpoint}")
        
        return {"status": "success"}


# Example usage
if __name__ == "__main__":
    # Initialize connector
    connector = FPSConnector({
        "api_key": "test_key",
        "participant_id": "TEST123"
    })
    
    # Example 1: Validate account
    print("=== Account Validation ===")
    validation = connector.validate_account("123456", "12345678", "John Doe")
    print(f"Valid: {validation['valid']}")
    if validation['valid']:
        print(f"Bank: {validation['bank_name']}")
    
    # Example 2: Initiate payment
    print("\n=== Initiate Payment ===")
    result = connector.initiate_payment(
        amount=Decimal("100.00"),
        sender_sort_code="123456",
        sender_account_number="12345678",
        sender_name="John Doe",
        beneficiary_sort_code="654321",
        beneficiary_account_number="87654321",
        beneficiary_name="Jane Smith",
        reference="Invoice 12345"
    )
    
    if result["success"]:
        payment = result["payment"]
        print(f"Payment ID: {payment['payment_id']}")
        print(f"Status: {payment['status']}")
        print(f"FPS Transaction ID: {payment['fps_transaction_id']}")
        print(f"Estimated completion: {payment['estimated_completion']}")

