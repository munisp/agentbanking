"""
Integration Tests for POS Services
End-to-end testing of POS system integration
"""

import pytest
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from decimal import Decimal

# Test configuration
TEST_BASE_URL = "http://localhost:8070"  # POS service URL
QR_SERVICE_URL = "http://localhost:8071"  # QR validation service URL
ENHANCED_POS_URL = "http://localhost:8072"  # Enhanced POS service URL
DEVICE_MANAGER_URL = "http://localhost:8073"  # Device manager URL

class TestPOSIntegration:
    """Integration tests for POS system"""
    
    @pytest.fixture
    async def http_client(self):
        """Create HTTP client for testing"""
        async with aiohttp.ClientSession() as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_pos_service_health(self, http_client):
        """Test POS service health check"""
        async with http_client.get(f"{TEST_BASE_URL}/health") as response:
            assert response.status == 200
            data = await response.json()
            assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_device_registration_flow(self, http_client):
        """Test complete device registration flow"""
        # Register a new device
        device_data = {
            "device_id": "TEST_DEVICE_001",
            "device_type": "CARD_READER",
            "protocol": "SERIAL",
            "connection_params": {
                "port": "/dev/ttyUSB0",
                "baudrate": 9600
            },
            "capabilities": ["READ_CARD", "PIN_ENTRY"]
        }
        
        async with http_client.post(
            f"{DEVICE_MANAGER_URL}/devices/register",
            json=device_data
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["success"] is True
            assert result["data"]["device_id"] == "TEST_DEVICE_001"
        
        # List devices to verify registration
        async with http_client.get(f"{DEVICE_MANAGER_URL}/devices") as response:
            assert response.status == 200
            devices = await response.json()
            device_ids = [device["device_id"] for device in devices]
            assert "TEST_DEVICE_001" in device_ids
        
        # Connect to device
        async with http_client.post(
            f"{DEVICE_MANAGER_URL}/devices/TEST_DEVICE_001/connect"
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_qr_code_generation_and_validation(self, http_client):
        """Test QR code generation and validation flow"""
        # Generate QR code
        qr_data = {
            "merchant_id": "MERCHANT_TEST_001",
            "amount": 150.75,
            "currency": "USD",
            "transaction_id": f"TXN_{int(datetime.now().timestamp())}",
            "description": "Integration test payment"
        }
        
        async with http_client.post(
            f"{QR_SERVICE_URL}/qr/generate",
            json=qr_data
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["success"] is True
            assert "qr_code" in result
            assert "qr_data" in result
            
            generated_qr_data = result["qr_data"]
        
        # Validate the generated QR code
        async with http_client.post(
            f"{QR_SERVICE_URL}/qr/validate",
            json={"qr_data": generated_qr_data}
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["valid"] is True
            assert result["security_score"] > 70
    
    @pytest.mark.asyncio
    async def test_payment_processing_flow(self, http_client):
        """Test complete payment processing flow"""
        # Create payment request
        payment_data = {
            "amount": 99.99,
            "currency": "USD",
            "payment_method": "card_chip",
            "merchant_id": "MERCHANT_TEST_001",
            "terminal_id": "TERMINAL_TEST_001",
            "card_details": {
                "card_number": "4242424242424242",  # Test card
                "expiry_month": "12",
                "expiry_year": "2025",
                "cvv": "123"
            }
        }
        
        # Process payment through enhanced POS service
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/process-payment",
            json=payment_data
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["success"] is True
            assert "transaction_id" in result
            assert result["amount"] == 99.99
            assert result["status"] in ["APPROVED", "PENDING"]
            
            transaction_id = result["transaction_id"]
        
        # Get transaction status
        async with http_client.get(
            f"{ENHANCED_POS_URL}/enhanced/transaction/{transaction_id}/status"
        ) as response:
            assert response.status == 200
            status = await response.json()
            assert "transaction_id" in status
            assert "status" in status
    
    @pytest.mark.asyncio
    async def test_fraud_detection_integration(self, http_client):
        """Test fraud detection integration"""
        # Create suspicious payment (high amount)
        suspicious_payment = {
            "amount": 9999.99,  # High amount to trigger fraud detection
            "currency": "USD",
            "payment_method": "card_chip",
            "merchant_id": "MERCHANT_TEST_001",
            "terminal_id": "TERMINAL_TEST_001"
        }
        
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/process-payment",
            json=suspicious_payment
        ) as response:
            result = await response.json()
            
            # Should either be declined or flagged for review
            if result.get("success"):
                # If approved, should have fraud score
                assert "fraud_score" in result
                assert result["fraud_score"] > 0
            else:
                # If declined, should mention fraud detection
                assert "fraud" in result.get("error", "").lower() or "risk" in result.get("error", "").lower()
    
    @pytest.mark.asyncio
    async def test_multi_currency_support(self, http_client):
        """Test multi-currency payment processing"""
        currencies = ["USD", "EUR", "GBP"]
        
        for currency in currencies:
            payment_data = {
                "amount": 100.0,
                "currency": currency,
                "payment_method": "card_contactless",
                "merchant_id": "MERCHANT_TEST_001",
                "terminal_id": "TERMINAL_TEST_001"
            }
            
            async with http_client.post(
                f"{ENHANCED_POS_URL}/enhanced/process-payment",
                json=payment_data
            ) as response:
                assert response.status == 200
                result = await response.json()
                assert result["currency"] == currency
    
    @pytest.mark.asyncio
    async def test_exchange_rate_integration(self, http_client):
        """Test exchange rate service integration"""
        # Get exchange rate
        async with http_client.get(
            f"{ENHANCED_POS_URL}/enhanced/exchange-rate/USD/EUR"
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert "rate" in result
            assert "from_currency" in result
            assert "to_currency" in result
            assert result["from_currency"] == "USD"
            assert result["to_currency"] == "EUR"
            assert float(result["rate"]) > 0
        
        # Convert amount
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/convert-amount",
            json={
                "amount": 100.0,
                "from_currency": "USD",
                "to_currency": "EUR"
            }
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert "converted_amount" in result
            assert float(result["converted_amount"]) > 0
    
    @pytest.mark.asyncio
    async def test_analytics_and_reporting(self, http_client):
        """Test analytics and reporting endpoints"""
        # Get transaction analytics
        async with http_client.get(
            f"{ENHANCED_POS_URL}/enhanced/analytics/transactions"
        ) as response:
            assert response.status == 200
            analytics = await response.json()
            assert "total_transactions" in analytics
            assert "total_amount" in analytics
            assert "success_rate" in analytics
        
        # Get fraud analytics
        async with http_client.get(
            f"{ENHANCED_POS_URL}/enhanced/analytics/fraud"
        ) as response:
            assert response.status == 200
            fraud_analytics = await response.json()
            assert "fraud_detected" in fraud_analytics
            assert "fraud_rate" in fraud_analytics
    
    @pytest.mark.asyncio
    async def test_device_health_monitoring(self, http_client):
        """Test device health monitoring"""
        # Get device statistics
        async with http_client.get(
            f"{DEVICE_MANAGER_URL}/devices/statistics"
        ) as response:
            assert response.status == 200
            stats = await response.json()
            assert "total_devices" in stats
            assert "connected_devices" in stats
            assert "device_types" in stats
        
        # Trigger device discovery
        async with http_client.get(
            f"{DEVICE_MANAGER_URL}/devices/discover"
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, http_client):
        """Test error handling and recovery mechanisms"""
        # Test invalid payment data
        invalid_payment = {
            "amount": -100.0,  # Invalid negative amount
            "currency": "INVALID",  # Invalid currency
            "payment_method": "invalid_method"
        }
        
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/process-payment",
            json=invalid_payment
        ) as response:
            assert response.status == 400
            result = await response.json()
            assert "error" in result
        
        # Test invalid QR data
        async with http_client.post(
            f"{QR_SERVICE_URL}/qr/validate",
            json={"qr_data": "invalid_qr_data"}
        ) as response:
            assert response.status == 200
            result = await response.json()
            assert result["valid"] is False
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, http_client):
        """Test rate limiting functionality"""
        # Make multiple rapid requests to test rate limiting
        tasks = []
        for i in range(20):  # Exceed rate limit
            task = http_client.get(f"{QR_SERVICE_URL}/qr/health")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some requests should be rate limited
        status_codes = []
        for response in responses:
            if isinstance(response, aiohttp.ClientResponse):
                status_codes.append(response.status)
                response.close()
        
        # Should have some 429 (Too Many Requests) responses
        assert 429 in status_codes or len([s for s in status_codes if s == 200]) < 20
    
    @pytest.mark.asyncio
    async def test_webhook_endpoints(self, http_client):
        """Test webhook endpoints for payment processors"""
        # Test Stripe webhook endpoint
        stripe_webhook_data = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_123456789",
                    "status": "succeeded"
                }
            }
        }
        
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/webhooks/stripe",
            json=stripe_webhook_data,
            headers={"Stripe-Signature": "test_signature"}
        ) as response:
            assert response.status in [200, 400]  # 400 if signature validation fails
        
        # Test Square webhook endpoint
        square_webhook_data = {
            "type": "payment.updated",
            "data": {
                "object": {
                    "payment": {
                        "id": "sq_payment_123456789",
                        "status": "COMPLETED"
                    }
                }
            }
        }
        
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/webhooks/square",
            json=square_webhook_data
        ) as response:
            assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, http_client):
        """Test performance benchmarks"""
        # Test QR generation performance
        start_time = datetime.now()
        
        qr_data = {
            "merchant_id": "PERF_TEST_MERCHANT",
            "amount": 50.0,
            "currency": "USD",
            "transaction_id": f"PERF_TXN_{int(datetime.now().timestamp())}"
        }
        
        async with http_client.post(
            f"{QR_SERVICE_URL}/qr/generate",
            json=qr_data
        ) as response:
            assert response.status == 200
            
        qr_generation_time = (datetime.now() - start_time).total_seconds()
        assert qr_generation_time < 1.0  # Should be under 1 second
        
        # Test payment processing performance
        start_time = datetime.now()
        
        payment_data = {
            "amount": 25.0,
            "currency": "USD",
            "payment_method": "card_chip",
            "merchant_id": "PERF_TEST_MERCHANT",
            "terminal_id": "PERF_TEST_TERMINAL"
        }
        
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/process-payment",
            json=payment_data
        ) as response:
            assert response.status == 200
            
        payment_processing_time = (datetime.now() - start_time).total_seconds()
        assert payment_processing_time < 5.0  # Should be under 5 seconds

class TestServiceInteroperability:
    """Test interoperability between different services"""
    
    @pytest.fixture
    async def http_client(self):
        """Create HTTP client for testing"""
        async with aiohttp.ClientSession() as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_cross_service_communication(self, http_client):
        """Test communication between different services"""
        # Generate QR code in QR service
        qr_data = {
            "merchant_id": "CROSS_SERVICE_TEST",
            "amount": 75.0,
            "currency": "USD",
            "transaction_id": f"CROSS_TXN_{int(datetime.now().timestamp())}"
        }
        
        async with http_client.post(
            f"{QR_SERVICE_URL}/qr/generate",
            json=qr_data
        ) as response:
            assert response.status == 200
            qr_result = await response.json()
        
        # Process QR payment through enhanced POS service
        payment_data = {
            "qr_data": qr_result["qr_data"],
            "payment_method": "qr_code"
        }
        
        async with http_client.post(
            f"{ENHANCED_POS_URL}/enhanced/process-qr-payment",
            json=payment_data
        ) as response:
            assert response.status == 200
            payment_result = await response.json()
            assert payment_result["success"] is True

# Test utilities
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
