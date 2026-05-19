#!/usr/bin/env python3
"""
Payment Validation Rules
Comprehensive validation for payment transactions
"""

import re
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PaymentValidator:
    def __init__(self) -> None:
        # Supported currencies and their validation rules
        self.currency_rules = {
            "NGN": {"min": 100, "max": 10000000, "decimals": 2},
            "USD": {"min": 1, "max": 100000, "decimals": 2},
            "EUR": {"min": 1, "max": 100000, "decimals": 2},
            "GBP": {"min": 1, "max": 100000, "decimals": 2},
            "CNY": {"min": 10, "max": 1000000, "decimals": 2},
            "BRL": {"min": 5, "max": 500000, "decimals": 2},
            "INR": {"min": 100, "max": 5000000, "decimals": 2},
            "GHS": {"min": 10, "max": 1000000, "decimals": 2},
            "KES": {"min": 100, "max": 10000000, "decimals": 2},
            "ZAR": {"min": 10, "max": 1000000, "decimals": 2}
        }
        
        # Country-specific validation patterns
        self.country_patterns = {
            "NG": {
                "phone": r"^\+234[0-9]{10}$",
                "bank_account": r"^[0-9]{10}$",
                "bvn": r"^[0-9]{11}$"
            },
            "US": {
                "phone": r"^\+1[0-9]{10}$",
                "ssn": r"^[0-9]{3}-[0-9]{2}-[0-9]{4}$",
                "routing": r"^[0-9]{9}$"
            },
            "BR": {
                "phone": r"^\+55[0-9]{10,11}$",
                "cpf": r"^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$",
                "pix": r"^[a-zA-Z0-9@._-]+$"
            },
            "IN": {
                "phone": r"^\+91[0-9]{10}$",
                "ifsc": r"^[A-Z]{4}0[A-Z0-9]{6}$",
                "upi": r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+$"
            }
        }
    
    def validate_amount(self, amount: float, currency: str) -> Dict[str, Any]:
        """Validate payment amount"""
        if currency not in self.currency_rules:
            return {
                "valid": False,
                "error": f"Unsupported currency: {currency}"
            }
        
        rules = self.currency_rules[currency]
        
        if amount < rules["min"]:
            return {
                "valid": False,
                "error": f"Amount below minimum for {currency}: {rules['min']}"
            }
        
        if amount > rules["max"]:
            return {
                "valid": False,
                "error": f"Amount exceeds maximum for {currency}: {rules['max']}"
            }
        
        # Check decimal places
        decimal_places = len(str(amount).split('.')[-1]) if '.' in str(amount) else 0
        if decimal_places > rules["decimals"]:
            return {
                "valid": False,
                "error": f"Too many decimal places for {currency}: max {rules['decimals']}"
            }
        
        return {"valid": True}
    
    def validate_recipient(self, recipient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate recipient information"""
        required_fields = ['name', 'country', 'account_info']
        
        for field in required_fields:
            if field not in recipient_data:
                return {
                    "valid": False,
                    "error": f"Missing required field: {field}"
                }
        
        # Validate name
        name = recipient_data.get('name', '').strip()
        if len(name) < 2:
            return {
                "valid": False,
                "error": "Recipient name too short"
            }
        
        # Country-specific validation
        country = recipient_data.get('country')
        if country in self.country_patterns:
            patterns = self.country_patterns[country]
            account_info = recipient_data.get('account_info', {})
            
            # Validate phone if provided
            if 'phone' in account_info:
                phone = account_info['phone']
                if not re.match(patterns.get('phone', ''), phone):
                    return {
                        "valid": False,
                        "error": f"Invalid phone format for {country}"
                    }
        
        return {"valid": True}
    
    def validate_sender(self, sender_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate sender information"""
        required_fields = ['user_id', 'country']
        
        for field in required_fields:
            if field not in sender_data:
                return {
                    "valid": False,
                    "error": f"Missing required field: {field}"
                }
        
        return {"valid": True}
    
    def validate_compliance(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate compliance requirements"""
        amount = payment_data.get('amount', 0)
        sender_country = payment_data.get('sender', {}).get('country')
        recipient_country = payment_data.get('recipient', {}).get('country')
        
        # High-value transaction checks
        if amount > 10000:  # USD equivalent
            if 'purpose' not in payment_data:
                return {
                    "valid": False,
                    "error": "Purpose required for high-value transactions"
                }
        
        # Cross-border compliance
        if sender_country != recipient_country:
            if 'compliance_info' not in payment_data:
                return {
                    "valid": False,
                    "error": "Compliance information required for cross-border payments"
                }
        
        return {"valid": True}
    
    def validate_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive payment validation"""
        validations = [
            self.validate_amount(payment_data.get('amount'), payment_data.get('currency')),
            self.validate_sender(payment_data.get('sender', {})),
            self.validate_recipient(payment_data.get('recipient', {})),
            self.validate_compliance(payment_data)
        ]
        
        for validation in validations:
            if not validation['valid']:
                return validation
        
        return {"valid": True, "message": "Payment validation passed"}

class ComplianceChecker:
    def __init__(self) -> None:
        # AML/CTF risk scoring factors
        self.risk_factors = {
            "high_risk_countries": ["AF", "IR", "KP", "SY"],  # Example high-risk countries
            "high_value_threshold": 10000,
            "velocity_limits": {
                "daily": 50000,
                "monthly": 200000
            }
        }
    
    def check_sanctions(self, entity_name: str, country: str) -> Dict[str, Any]:
        """Check against sanctions lists (simplified)"""
        # In production, integrate with actual sanctions databases
        high_risk_keywords = ["terrorist", "sanctioned", "blocked"]
        
        entity_lower = entity_name.lower()
        for keyword in high_risk_keywords:
            if keyword in entity_lower:
                return {
                    "passed": False,
                    "risk_level": "HIGH",
                    "reason": f"Entity name contains high-risk keyword: {keyword}"
                }
        
        if country in self.risk_factors["high_risk_countries"]:
            return {
                "passed": False,
                "risk_level": "HIGH",
                "reason": f"High-risk country: {country}"
            }
        
        return {"passed": True, "risk_level": "LOW"}
    
    def calculate_risk_score(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate transaction risk score"""
        score = 0
        factors = []
        
        amount = payment_data.get('amount', 0)
        sender = payment_data.get('sender', {})
        recipient = payment_data.get('recipient', {})
        
        # Amount-based risk
        if amount > self.risk_factors["high_value_threshold"]:
            score += 30
            factors.append("High value transaction")
        
        # Country risk
        sender_country = sender.get('country')
        recipient_country = recipient.get('country')
        
        if sender_country in self.risk_factors["high_risk_countries"]:
            score += 40
            factors.append("High-risk sender country")
        
        if recipient_country in self.risk_factors["high_risk_countries"]:
            score += 40
            factors.append("High-risk recipient country")
        
        # Cross-border risk
        if sender_country != recipient_country:
            score += 10
            factors.append("Cross-border transaction")
        
        # Determine risk level
        if score >= 70:
            risk_level = "HIGH"
        elif score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "risk_score": score,
            "risk_level": risk_level,
            "risk_factors": factors,
            "requires_review": score >= 40
        }
