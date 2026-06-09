"""
Unit Tests for QR Validation Service
Comprehensive test coverage for QR code validation and processing
"""

import pytest
import asyncio
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

# Import the modules to test
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qr_validation_service import QRValidationService, QRCodeData, FraudRule, SecurityLevel

class TestQRValidationService:
    """Test cases for QR Validation Service"""
    
    @pytest.fixture
    async def qr_service(self):
        """Create QR validation service instance for testing"""
        service = QRValidationService()
        
        # Mock Redis client
        service.redis_client = AsyncMock()
        service.redis_client.ping = AsyncMock(return_value=True)
        service.redis_client.get = AsyncMock(return_value=None)
        service.redis_client.setex = AsyncMock(return_value=True)
        service.redis_client.incr = AsyncMock(return_value=1)
        service.redis_client.expire = AsyncMock(return_value=True)
        
        await service.initialize()
        return service
    
    @pytest.fixture
    def valid_qr_data(self):
        """Create valid QR code data for testing"""
        return {
            "merchant_id": "MERCHANT_123",
            "amount": 100.50,
            "currency": "USD",
            "transaction_id": "TXN_456",
            "timestamp": int(datetime.utcnow().timestamp()),
            "expiry": int((datetime.utcnow() + timedelta(minutes=15)).timestamp()),
            "description": "Test payment"
        }
    
    def test_qr_code_data_validation(self, valid_qr_data):
        """Test QR code data validation"""
        # Valid data should pass
        qr_data = QRCodeData(**valid_qr_data)
        assert qr_data.merchant_id == "MERCHANT_123"
        assert qr_data.amount == Decimal("100.50")
        assert qr_data.currency == "USD"
        
        # Invalid amount should fail
        invalid_data = valid_qr_data.copy()
        invalid_data["amount"] = -10.0
        with pytest.raises(ValueError):
            QRCodeData(**invalid_data)
        
        # Invalid currency should fail
        invalid_data = valid_qr_data.copy()
        invalid_data["currency"] = "INVALID"
        with pytest.raises(ValueError):
            QRCodeData(**invalid_data)
    
    @pytest.mark.asyncio
    async def test_generate_qr_code(self, qr_service, valid_qr_data):
        """Test QR code generation"""
        qr_data = QRCodeData(**valid_qr_data)
        
        result = await qr_service.generate_qr_code(qr_data)
        
        assert result["success"] is True
        assert "qr_code" in result
        assert "qr_data" in result
        assert result["security_level"] == SecurityLevel.HIGH
        
        # Verify QR code contains expected data
        qr_code_data = json.loads(result["qr_data"])
        assert qr_code_data["merchant_id"] == "MERCHANT_123"
        assert qr_code_data["amount"] == 100.50
    
    @pytest.mark.asyncio
    async def test_qr_code_signature_validation(self, qr_service, valid_qr_data):
        """Test QR code digital signature validation"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # Generate QR code with signature
        result = await qr_service.generate_qr_code(qr_data)
        qr_code_data = json.loads(result["qr_data"])
        
        # Valid signature should pass validation
        is_valid = await qr_service._validate_signature(qr_code_data)
        assert is_valid is True
        
        # Tampered data should fail validation
        qr_code_data["amount"] = 999.99
        is_valid = await qr_service._validate_signature(qr_code_data)
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_qr_code_expiration(self, qr_service, valid_qr_data):
        """Test QR code expiration validation"""
        # Expired QR code
        expired_data = valid_qr_data.copy()
        expired_data["expiry"] = int((datetime.utcnow() - timedelta(minutes=1)).timestamp())
        
        qr_data = QRCodeData(**expired_data)
        result = await qr_service.validate_qr_code(json.dumps(expired_data))
        
        assert result["valid"] is False
        assert "expired" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_fraud_detection_rules(self, qr_service, valid_qr_data):
        """Test fraud detection rules"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # Test high amount rule
        high_amount_data = valid_qr_data.copy()
        high_amount_data["amount"] = 10000.0  # Trigger high amount rule
        
        fraud_score = await qr_service._calculate_fraud_score(QRCodeData(**high_amount_data))
        assert fraud_score > 0  # Should trigger fraud rules
        
        # Test velocity rule (mock multiple transactions)
        qr_service.redis_client.get.return_value = "5"  # Mock 5 previous transactions
        fraud_score = await qr_service._calculate_fraud_score(qr_data)
        assert fraud_score > 0  # Should trigger velocity rule
    
    @pytest.mark.asyncio
    async def test_duplicate_transaction_detection(self, qr_service, valid_qr_data):
        """Test duplicate transaction detection"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # First validation should succeed
        qr_service.redis_client.get.return_value = None  # No previous transaction
        result = await qr_service.validate_qr_code(json.dumps(valid_qr_data))
        assert result["valid"] is True
        
        # Second validation with same transaction_id should fail
        qr_service.redis_client.get.return_value = "processed"  # Mock duplicate
        result = await qr_service.validate_qr_code(json.dumps(valid_qr_data))
        assert result["valid"] is False
        assert "duplicate" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_security_scoring(self, qr_service, valid_qr_data):
        """Test security scoring algorithm"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # Normal transaction should have high security score
        security_score = await qr_service._calculate_security_score(qr_data)
        assert 70 <= security_score <= 100
        
        # High amount should reduce security score
        high_amount_data = valid_qr_data.copy()
        high_amount_data["amount"] = 5000.0
        high_amount_qr = QRCodeData(**high_amount_data)
        
        high_amount_score = await qr_service._calculate_security_score(high_amount_qr)
        assert high_amount_score < security_score
    
    @pytest.mark.asyncio
    async def test_qr_code_encryption_decryption(self, qr_service, valid_qr_data):
        """Test QR code encryption and decryption"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # Test encryption
        encrypted_data = await qr_service._encrypt_qr_data(valid_qr_data, "test_password")
        assert encrypted_data != json.dumps(valid_qr_data)
        assert "encrypted_data" in encrypted_data
        assert "salt" in encrypted_data
        
        # Test decryption
        decrypted_data = await qr_service._decrypt_qr_data(encrypted_data, "test_password")
        assert decrypted_data == valid_qr_data
        
        # Wrong password should fail
        with pytest.raises(Exception):
            await qr_service._decrypt_qr_data(encrypted_data, "wrong_password")
    
    @pytest.mark.asyncio
    async def test_merchant_validation(self, qr_service, valid_qr_data):
        """Test merchant validation"""
        # Mock merchant cache
        qr_service.merchant_cache = {
            "MERCHANT_123": {
                "name": "Test Merchant",
                "status": "active",
                "risk_level": "low"
            }
        }
        
        qr_data = QRCodeData(**valid_qr_data)
        
        # Valid merchant should pass
        is_valid = await qr_service._validate_merchant(qr_data.merchant_id)
        assert is_valid is True
        
        # Invalid merchant should fail
        invalid_merchant_data = valid_qr_data.copy()
        invalid_merchant_data["merchant_id"] = "INVALID_MERCHANT"
        
        is_valid = await qr_service._validate_merchant("INVALID_MERCHANT")
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, qr_service, valid_qr_data):
        """Test rate limiting functionality"""
        client_id = "test_client"
        
        # Mock rate limit not exceeded
        qr_service.redis_client.incr.return_value = 5  # Under limit
        
        is_allowed = await qr_service._check_rate_limit(client_id)
        assert is_allowed is True
        
        # Mock rate limit exceeded
        qr_service.redis_client.incr.return_value = 101  # Over limit
        
        is_allowed = await qr_service._check_rate_limit(client_id)
        assert is_allowed is False
    
    @pytest.mark.asyncio
    async def test_qr_analytics(self, qr_service, valid_qr_data):
        """Test QR code analytics tracking"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # Mock analytics data
        qr_service.redis_client.hgetall.return_value = {
            "total_generated": "100",
            "total_validated": "95",
            "fraud_detected": "2",
            "success_rate": "95.0"
        }
        
        analytics = await qr_service.get_qr_analytics()
        
        assert analytics["total_generated"] == 100
        assert analytics["total_validated"] == 95
        assert analytics["fraud_detected"] == 2
        assert analytics["success_rate"] == 95.0
    
    def test_fraud_rules_configuration(self, qr_service):
        """Test fraud rules configuration"""
        rules = qr_service.fraud_rules
        
        # Should have all expected fraud rules
        rule_types = [rule.rule_type for rule in rules]
        expected_rules = [
            "high_amount", "velocity", "unusual_time", "duplicate_merchant",
            "suspicious_pattern", "geographic_anomaly", "device_fingerprint"
        ]
        
        for expected_rule in expected_rules:
            assert expected_rule in rule_types
        
        # Each rule should have proper configuration
        for rule in rules:
            assert rule.threshold > 0
            assert rule.weight > 0
            assert rule.description is not None
    
    @pytest.mark.asyncio
    async def test_error_handling(self, qr_service):
        """Test error handling in various scenarios"""
        # Test with invalid JSON
        result = await qr_service.validate_qr_code("invalid_json")
        assert result["valid"] is False
        assert "error" in result
        
        # Test with missing required fields
        incomplete_data = {"merchant_id": "TEST"}
        result = await qr_service.validate_qr_code(json.dumps(incomplete_data))
        assert result["valid"] is False
        
        # Test Redis connection failure
        qr_service.redis_client.ping.side_effect = Exception("Redis connection failed")
        
        # Service should handle Redis failures gracefully
        result = await qr_service.validate_qr_code(json.dumps({"merchant_id": "TEST", "amount": 100}))
        # Should not crash, but may have reduced functionality
        assert "error" in result or "valid" in result
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self, qr_service, valid_qr_data):
        """Test performance metrics collection"""
        qr_data = QRCodeData(**valid_qr_data)
        
        # Generate QR code and measure performance
        start_time = datetime.utcnow()
        result = await qr_service.generate_qr_code(qr_data)
        end_time = datetime.utcnow()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # QR generation should be fast (under 1 second)
        assert processing_time < 1.0
        assert result["success"] is True
        
        # Validation should also be fast
        start_time = datetime.utcnow()
        validation_result = await qr_service.validate_qr_code(result["qr_data"])
        end_time = datetime.utcnow()
        
        validation_time = (end_time - start_time).total_seconds()
        assert validation_time < 0.5  # Validation should be even faster

# Test fixtures and utilities
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
