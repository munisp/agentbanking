#!/usr/bin/env python3
"""
SEPA Instant Integration - Europe
Real-time payment system for EUR transfers across SEPA zone
"""

from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
import logging
import uuid
import re

logger = logging.getLogger(__name__)


class SEPAInstantConnector:
    """
    Connector for SEPA Instant Credit Transfer (SCT Inst)
    
    SEPA Instant enables real-time EUR transfers across 36 European countries
    Available 24/7/365, settlement within 10 seconds
    """
    
    # SEPA Instant transaction limits
    MAX_TRANSACTION_AMOUNT = Decimal("100000.00")  # €100,000 per transaction
    MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    
    # IBAN validation pattern (simplified)
    IBAN_PATTERN = re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$')
    
    # BIC/SWIFT validation pattern
    BIC_PATTERN = re.compile(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$')
    
    # SEPA countries
    SEPA_COUNTRIES = [
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
        "DE", "GR", "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU",
        "MT", "MC", "NL", "NO", "PL", "PT", "RO", "SM", "SK", "SI",
        "ES", "SE", "CH", "GB", "VA", "AD"
    ]
    
    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        Initialize SEPA Instant connector
        
        Args:
            config: Configuration including API credentials
        """
        self.config = config or {}
        self.api_url = self.config.get("api_url", "https://api.sepainstant.eu/v1")
        self.api_key = self.config.get("api_key")
        self.bic = self.config.get("bic")  # Bank Identifier Code
        
        if not self.api_key or not self.bic:
            logger.warning("SEPA Instant credentials not configured")
    
    def validate_iban(self, iban: str) -> Dict:
        """
        Validate IBAN (International Bank Account Number)
        
        Args:
            iban: IBAN to validate
            
        Returns:
            Validation result with details
        """
        # Remove spaces and convert to uppercase
        iban = iban.replace(" ", "").upper()
        
        # Check format
        if not self.IBAN_PATTERN.match(iban):
            return {
                "valid": False,
                "error": "Invalid IBAN format"
            }
        
        # Extract country code
        country_code = iban[:2]
        
        # Check if country is in SEPA zone
        if country_code not in self.SEPA_COUNTRIES:
            return {
                "valid": False,
                "error": f"Country {country_code} is not in SEPA zone"
            }
        
        # Validate checksum (mod-97 algorithm)
        # Move first 4 characters to end
        rearranged = iban[4:] + iban[:4]
        
        # Replace letters with numbers (A=10, B=11, ..., Z=35)
        numeric = ""
        for char in rearranged:
            if char.isdigit():
                numeric += char
            else:
                numeric += str(ord(char) - ord('A') + 10)
        
        # Calculate mod 97
        checksum = int(numeric) % 97
        
        if checksum != 1:
            return {
                "valid": False,
                "error": "Invalid IBAN checksum"
            }
        
        return {
            "valid": True,
            "iban": iban,
            "country": country_code,
            "country_name": self._get_country_name(country_code),
            "bank_code": self._extract_bank_code(iban),
            "verified_at": datetime.utcnow().isoformat()
        }
    
    def validate_bic(self, bic: str) -> Dict:
        """
        Validate BIC/SWIFT code
        
        Args:
            bic: BIC/SWIFT code
            
        Returns:
            Validation result
        """
        bic = bic.replace(" ", "").upper()
        
        if not self.BIC_PATTERN.match(bic):
            return {
                "valid": False,
                "error": "Invalid BIC format"
            }
        
        return {
            "valid": True,
            "bic": bic,
            "bank_code": bic[:4],
            "country_code": bic[4:6],
            "location_code": bic[6:8],
            "branch_code": bic[8:11] if len(bic) == 11 else None
        }
    
    def initiate_payment(
        self,
        amount: Decimal,
        sender_iban: str,
        sender_name: str,
        beneficiary_iban: str,
        beneficiary_name: str,
        sender_bic: Optional[str] = None,
        beneficiary_bic: Optional[str] = None,
        remittance_info: Optional[str] = None,
        end_to_end_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Initiate SEPA Instant payment
        
        Args:
            amount: Payment amount in EUR
            sender_iban: Sender's IBAN
            sender_name: Sender's name (max 70 chars)
            sender_bic: Sender's BIC (optional for SEPA zone)
            beneficiary_iban: Beneficiary's IBAN
            beneficiary_name: Beneficiary's name (max 70 chars)
            beneficiary_bic: Beneficiary's BIC (optional)
            remittance_info: Payment reference (max 140 chars)
            end_to_end_id: Unique transaction ID (max 35 chars)
            metadata: Additional metadata
            
        Returns:
            Payment initiation result
        """
        # Validate amount
        if amount < self.MIN_TRANSACTION_AMOUNT:
            return {
                "success": False,
                "error": f"Amount must be at least €{self.MIN_TRANSACTION_AMOUNT}"
            }
        
        if amount > self.MAX_TRANSACTION_AMOUNT:
            return {
                "success": False,
                "error": f"Amount exceeds SEPA Instant maximum of €{self.MAX_TRANSACTION_AMOUNT}"
            }
        
        # Validate sender IBAN
        sender_validation = self.validate_iban(sender_iban)
        if not sender_validation["valid"]:
            return {
                "success": False,
                "error": "Invalid sender IBAN",
                "details": sender_validation["error"]
            }
        
        # Validate beneficiary IBAN
        beneficiary_validation = self.validate_iban(beneficiary_iban)
        if not beneficiary_validation["valid"]:
            return {
                "success": False,
                "error": "Invalid beneficiary IBAN",
                "details": beneficiary_validation["error"]
            }
        
        # Generate end-to-end ID if not provided
        if not end_to_end_id:
            end_to_end_id = f"E2E{uuid.uuid4().hex[:12].upper()}"
        
        # Truncate fields to SEPA limits
        sender_name = sender_name[:70]
        beneficiary_name = beneficiary_name[:70]
        if remittance_info:
            remittance_info = remittance_info[:140]
        
        # Generate payment ID
        payment_id = f"sepa_{uuid.uuid4().hex[:16]}"
        
        # Create payment request
        payment_request = {
            "payment_id": payment_id,
            "end_to_end_id": end_to_end_id,
            "amount": float(amount),
            "currency": "EUR",
            "sender": {
                "iban": sender_iban,
                "name": sender_name,
                "bic": sender_bic,
                "country": sender_validation["country"]
            },
            "beneficiary": {
                "iban": beneficiary_iban,
                "name": beneficiary_name,
                "bic": beneficiary_bic,
                "country": beneficiary_validation["country"]
            },
            "remittance_information": remittance_info or f"Payment {payment_id[:8]}",
            "metadata": metadata or {},
            "initiated_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "estimated_completion": "Within 10 seconds",
            "scheme": "SEPA Instant Credit Transfer"
        }
        
        # In production, call SEPA Instant API via bank/PSP
        # response = self._call_sepa_api("/payments", payment_request)
        
        # Simulate success
        payment_request["status"] = "processing"
        payment_request["transaction_id"] = f"TXN{uuid.uuid4().hex[:16].upper()}"
        payment_request["settlement_date"] = datetime.utcnow().date().isoformat()
        
        logger.info(f"SEPA Instant payment initiated: {payment_id}")
        
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
        # In production, call SEPA API
        # response = self._call_sepa_api(f"/payments/{payment_id}")
        
        # Simulate status
        return {
            "payment_id": payment_id,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "settlement_date": datetime.utcnow().date().isoformat(),
            "processing_time_seconds": 3
        }
    
    def request_payment_recall(
        self,
        payment_id: str,
        reason: str
    ) -> Dict:
        """
        Request payment recall (reversal)
        
        Note: Recall is not guaranteed and requires beneficiary bank cooperation
        
        Args:
            payment_id: Payment to recall
            reason: Reason for recall
            
        Returns:
            Recall request result
        """
        recall_id = f"recall_{uuid.uuid4().hex[:12]}"
        
        return {
            "recall_id": recall_id,
            "payment_id": payment_id,
            "status": "pending",
            "reason": reason,
            "requested_at": datetime.utcnow().isoformat(),
            "note": "Recall request submitted. Outcome depends on beneficiary bank."
        }
    
    def get_supported_countries(self) -> List[Dict]:
        """Get list of SEPA countries"""
        country_names = {
            "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
            "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia",
            "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
            "HU": "Hungary", "IS": "Iceland", "IE": "Ireland", "IT": "Italy",
            "LV": "Latvia", "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg",
            "MT": "Malta", "MC": "Monaco", "NL": "Netherlands", "NO": "Norway",
            "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SM": "San Marino",
            "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
            "CH": "Switzerland", "GB": "United Kingdom", "VA": "Vatican City", "AD": "Andorra"
        }
        
        return [
            {
                "code": code,
                "name": country_names.get(code, code),
                "sepa_instant_enabled": True
            }
            for code in self.SEPA_COUNTRIES
        ]
    
    def _get_country_name(self, country_code: str) -> str:
        """Get country name from code"""
        country_names = {
            "AT": "Austria", "BE": "Belgium", "DE": "Germany", "ES": "Spain",
            "FR": "France", "IT": "Italy", "NL": "Netherlands", "PT": "Portugal",
            "IE": "Ireland", "FI": "Finland", "GR": "Greece", "PL": "Poland"
        }
        return country_names.get(country_code, country_code)
    
    def _extract_bank_code(self, iban: str) -> str:
        """Extract bank code from IBAN (country-specific)"""
        country = iban[:2]
        
        # Simplified extraction (varies by country)
        if country == "DE":
            return iban[4:12]  # German bank code
        elif country == "FR":
            return iban[4:9]   # French bank code
        elif country == "IT":
            return iban[5:10]  # Italian bank code
        else:
            return iban[4:8]   # Generic
    
    def _call_sepa_api(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Call SEPA Instant API (placeholder)
        
        In production, integrate with bank/PSP SEPA Instant API
        """
        logger.info(f"SEPA API call: {endpoint}")
        return {"status": "success"}


# Example usage
if __name__ == "__main__":
    # Initialize connector
    connector = SEPAInstantConnector({
        "api_key": "test_key",
        "bic": "TESTDE12XXX"
    })
    
    # Example 1: Validate IBAN
    print("=== IBAN Validation ===")
    validation = connector.validate_iban("DE89370400440532013000")
    print(f"Valid: {validation['valid']}")
    if validation['valid']:
        print(f"Country: {validation['country_name']}")
        print(f"Bank Code: {validation['bank_code']}")
    
    # Example 2: Initiate payment
    print("\n=== Initiate SEPA Instant Payment ===")
    result = connector.initiate_payment(
        amount=Decimal("500.00"),
        sender_iban="DE89370400440532013000",
        sender_name="John Doe",
        beneficiary_iban="FR1420041010050500013M02606",
        beneficiary_name="Jane Smith",
        remittance_info="Invoice INV-2025-001"
    )
    
    if result["success"]:
        payment = result["payment"]
        print(f"Payment ID: {payment['payment_id']}")
        print(f"Transaction ID: {payment['transaction_id']}")
        print(f"Status: {payment['status']}")
        print(f"Estimated completion: {payment['estimated_completion']}")
    
    # Example 3: Get supported countries
    print("\n=== SEPA Countries ===")
    countries = connector.get_supported_countries()
    print(f"Total countries: {len(countries)}")
    print(f"Sample: {countries[:5]}")

