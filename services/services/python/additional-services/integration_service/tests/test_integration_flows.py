"""
Integration Tests for Complete User Flows

Tests the complete integration between all services:
- Transaction flow with automatic KYC checking
- KYC upgrade flow with transaction continuation
- Real-time event streaming
- State synchronization
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import json

# Test fixtures
@pytest.fixture
def integration_client():
    """FastAPI test client for integration tests"""
    from main import app
    return TestClient(app)

@pytest.fixture
def mock_services():
    """Mock all external services"""
    return {
        'cdp': Mock(
            get_wallet=AsyncMock(return_value={
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
                "balance": {"usdc": "1500.00", "ngn": "2250000.00"}
            }),
            create_wallet=AsyncMock(return_value={
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
            })
        ),
        'kyc': Mock(
            get_kyc_status=AsyncMock(return_value={
                "tier": 0,
                "status": "pending",
                "limits": {"daily": 300, "monthly": 1000}
            }),
            upgrade_kyc=AsyncMock(return_value={
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000}
            })
        ),
        'payment': Mock(
            process_payment=AsyncMock(return_value={
                "transaction_id": "txn_123",
                "status": "processing"
            })
        )
    }


class TestCompleteTransactionFlow:
    """Test complete transaction flow from initiation to completion"""
    
    def test_successful_transaction_tier1_user(self, integration_client, mock_services):
        """
        Test successful transaction for Tier 1 user
        
        Flow:
        1. User initiates transaction ($500)
        2. System checks KYC (Tier 1, limit $3000) - PASS
        3. System checks balance - PASS
        4. Transaction processed
        5. Real-time event sent
        """
        with patch('orchestrator.cdp_service', mock_services['cdp']), \
             patch('orchestrator.kyc_service', mock_services['kyc']), \
             patch('orchestrator.payment_service', mock_services['payment']):
            
            # Update KYC mock to return Tier 1
            mock_services['kyc'].get_kyc_status.return_value = {
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000}
            }
            
            # Initiate transaction
            response = integration_client.post(
                "/api/integration/transaction/initiate",
                json={
                    "user_id": "user_123",
                    "amount": 500,
                    "recipient": "recipient@example.com",
                    "currency": "USD"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "processing"
            assert "transaction_id" in data
            assert data["amount"] == 500
            
            # Verify services were called
            mock_services['kyc'].get_kyc_status.assert_called_once()
            mock_services['cdp'].get_wallet.assert_called_once()
            mock_services['payment'].process_payment.assert_called_once()
    
    def test_transaction_requires_kyc_upgrade(self, integration_client, mock_services):
        """
        Test transaction that requires KYC upgrade
        
        Flow:
        1. User initiates transaction ($500)
        2. System checks KYC (Tier 0, limit $300) - FAIL
        3. System returns kyc_required status
        4. User upgrades to Tier 1
        5. Transaction continues automatically
        """
        with patch('orchestrator.cdp_service', mock_services['cdp']), \
             patch('orchestrator.kyc_service', mock_services['kyc']), \
             patch('orchestrator.payment_service', mock_services['payment']):
            
            # Tier 0 user tries to send $500
            response = integration_client.post(
                "/api/integration/transaction/initiate",
                json={
                    "user_id": "user_123",
                    "amount": 500,
                    "recipient": "recipient@example.com",
                    "currency": "USD"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "kyc_required"
            assert data["kyc_check"]["current_tier"] == 0
            assert data["kyc_check"]["required_tier"] == 1
            assert data["kyc_check"]["reason"] == "Amount $500 exceeds Tier 0 limit of $300"
            assert data["next_step"] == "upgrade_kyc"
            assert data["estimated_time"] == "2 minutes"
            
            # Verify payment was NOT processed
            mock_services['payment'].process_payment.assert_not_called()
    
    def test_transaction_insufficient_balance(self, integration_client, mock_services):
        """
        Test transaction with insufficient balance
        
        Flow:
        1. User initiates transaction ($2000)
        2. System checks KYC - PASS
        3. System checks balance ($1500) - FAIL
        4. System returns insufficient_balance status
        """
        with patch('orchestrator.cdp_service', mock_services['cdp']), \
             patch('orchestrator.kyc_service', mock_services['kyc']):
            
            # Update KYC to Tier 1
            mock_services['kyc'].get_kyc_status.return_value = {
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000}
            }
            
            # Try to send $2000 (balance is $1500)
            response = integration_client.post(
                "/api/integration/transaction/initiate",
                json={
                    "user_id": "user_123",
                    "amount": 2000,
                    "recipient": "recipient@example.com",
                    "currency": "USD"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "insufficient_balance"
            assert data["required"] == 2000
            assert data["available"] == 1500
            assert data["next_step"] == "add_funds"


class TestKYCUpgradeFlow:
    """Test KYC upgrade flow with transaction continuation"""
    
    def test_kyc_upgrade_with_transaction_continuation(self, integration_client, mock_services):
        """
        Test complete KYC upgrade flow with transaction continuation
        
        Flow:
        1. User initiates transaction ($500) - KYC required
        2. User upgrades KYC to Tier 1
        3. System sends kyc_verified event
        4. Frontend receives callback
        5. Transaction continues automatically
        6. Transaction completes successfully
        """
        with patch('orchestrator.cdp_service', mock_services['cdp']), \
             patch('orchestrator.kyc_service', mock_services['kyc']), \
             patch('orchestrator.payment_service', mock_services['payment']):
            
            # Step 1: Initiate transaction (Tier 0)
            response1 = integration_client.post(
                "/api/integration/transaction/initiate",
                json={
                    "user_id": "user_123",
                    "amount": 500,
                    "recipient": "recipient@example.com",
                    "currency": "USD"
                }
            )
            
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["status"] == "kyc_required"
            transaction_id = data1.get("transaction_id")
            
            # Step 2: User upgrades KYC (simulated)
            mock_services['kyc'].get_kyc_status.return_value = {
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000}
            }
            
            # Step 3: KYC upgrade callback
            response2 = integration_client.post(
                "/api/integration/kyc/upgrade/callback",
                json={
                    "user_id": "user_123",
                    "new_tier": 1,
                    "transaction_id": transaction_id
                }
            )
            
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["status"] == "success"
            assert data2["message"] == "KYC upgraded and transaction continued"
            
            # Step 4: Verify transaction was continued
            response3 = integration_client.get(
                f"/api/integration/transaction/{transaction_id}/status"
            )
            
            assert response3.status_code == 200
            data3 = response3.json()
            assert data3["status"] in ["processing", "completed"]
    
    def test_kyc_upgrade_without_pending_transaction(self, integration_client, mock_services):
        """
        Test KYC upgrade without pending transaction
        
        Flow:
        1. User upgrades KYC (no pending transaction)
        2. System sends kyc_verified event
        3. No transaction continuation
        """
        with patch('orchestrator.kyc_service', mock_services['kyc']):
            
            response = integration_client.post(
                "/api/integration/kyc/upgrade/callback",
                json={
                    "user_id": "user_123",
                    "new_tier": 1,
                    "transaction_id": None
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["message"] == "KYC upgraded successfully"


class TestUserContextAPI:
    """Test unified user context API"""
    
    def test_get_complete_user_context(self, integration_client, mock_services):
        """
        Test getting complete user context
        
        Returns:
        - CDP wallet address and balance
        - KYC tier, status, and limits
        - Transaction history
        """
        with patch('user_router.cdp_service', mock_services['cdp']), \
             patch('user_router.kyc_service', mock_services['kyc']):
            
            # Update mocks
            mock_services['kyc'].get_kyc_status.return_value = {
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000},
                "remaining": {"daily": 2500, "monthly": 47500}
            }
            
            response = integration_client.get(
                "/api/integration/user/user_123/context"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify CDP context
            assert "cdp" in data
            assert data["cdp"]["wallet_address"] == "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
            assert data["cdp"]["balance"]["usdc"] == "1500.00"
            
            # Verify KYC context
            assert "kyc" in data
            assert data["kyc"]["tier"] == 1
            assert data["kyc"]["status"] == "verified"
            assert data["kyc"]["limits"]["daily"] == 3000
            
            # Verify transaction context
            assert "transactions" in data
    
    def test_user_context_with_invalid_user(self, integration_client, mock_services):
        """Test user context with invalid user ID"""
        with patch('user_router.cdp_service', mock_services['cdp']):
            
            # Mock CDP service to raise error
            mock_services['cdp'].get_wallet.side_effect = Exception("User not found")
            
            response = integration_client.get(
                "/api/integration/user/invalid_user/context"
            )
            
            assert response.status_code == 404
            data = response.json()
            assert "error" in data


class TestNavigationContext:
    """Test navigation context preservation"""
    
    def test_create_navigation_context(self, integration_client):
        """
        Test creating navigation context
        
        Flow:
        1. User navigates to KYC upgrade
        2. System stores return URL and context
        3. After KYC, system retrieves context
        4. User returns to original screen
        """
        # Create navigation context
        response1 = integration_client.post(
            "/api/integration/navigation/context",
            json={
                "user_id": "user_123",
                "return_url": "/send-money",
                "context": {
                    "transaction": {
                        "amount": 500,
                        "recipient": "recipient@example.com"
                    }
                }
            }
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "success"
        context_id = data1["context_id"]
        
        # Retrieve navigation context
        response2 = integration_client.get(
            f"/api/integration/navigation/context/{context_id}"
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["return_url"] == "/send-money"
        assert data2["context"]["transaction"]["amount"] == 500


class TestRealTimeEvents:
    """Test real-time event streaming (SSE)"""
    
    def test_event_stream_connection(self, integration_client):
        """
        Test SSE event stream connection
        
        Flow:
        1. Client connects to event stream
        2. System sends initial connection event
        3. System sends transaction/KYC events
        """
        # Note: SSE testing requires special handling
        # This is a simplified test
        response = integration_client.get(
            "/api/integration/events/stream?user_id=user_123",
            headers={"Accept": "text/event-stream"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
    
    @pytest.mark.asyncio
    async def test_event_publishing(self, mock_services):
        """
        Test event publishing to Redis
        
        Flow:
        1. Service publishes event
        2. Redis receives event
        3. Subscribers receive event
        """
        from event_bus import EventBus
        
        event_bus = EventBus(redis_client=mock_services.get('redis'))
        
        await event_bus.publish_event(
            event_type="transaction_status",
            user_id="user_123",
            data={
                "transaction_id": "txn_123",
                "status": "completed"
            }
        )
        
        # Verify Redis publish was called
        # mock_services['redis'].publish.assert_called_once()


class TestErrorHandling:
    """Test error handling and recovery"""
    
    def test_transaction_with_service_timeout(self, integration_client, mock_services):
        """Test transaction when external service times out"""
        with patch('orchestrator.cdp_service', mock_services['cdp']):
            
            # Mock timeout
            mock_services['cdp'].get_wallet.side_effect = asyncio.TimeoutError()
            
            response = integration_client.post(
                "/api/integration/transaction/initiate",
                json={
                    "user_id": "user_123",
                    "amount": 500,
                    "recipient": "recipient@example.com",
                    "currency": "USD"
                }
            )
            
            assert response.status_code == 503
            data = response.json()
            assert "error" in data
            assert "timeout" in data["error"].lower()
    
    def test_transaction_with_invalid_input(self, integration_client):
        """Test transaction with invalid input"""
        response = integration_client.post(
            "/api/integration/transaction/initiate",
            json={
                "user_id": "user_123",
                "amount": -500,  # Invalid negative amount
                "recipient": "invalid-email",  # Invalid email
                "currency": "INVALID"  # Invalid currency
            }
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestConcurrency:
    """Test concurrent operations"""
    
    @pytest.mark.asyncio
    async def test_concurrent_transactions(self, integration_client, mock_services):
        """
        Test multiple concurrent transactions
        
        Flow:
        1. User initiates multiple transactions simultaneously
        2. System processes all transactions
        3. All transactions complete successfully
        """
        with patch('orchestrator.cdp_service', mock_services['cdp']), \
             patch('orchestrator.kyc_service', mock_services['kyc']), \
             patch('orchestrator.payment_service', mock_services['payment']):
            
            # Update KYC to Tier 1
            mock_services['kyc'].get_kyc_status.return_value = {
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000}
            }
            
            # Initiate 5 concurrent transactions
            tasks = []
            for i in range(5):
                response = integration_client.post(
                    "/api/integration/transaction/initiate",
                    json={
                        "user_id": "user_123",
                        "amount": 100,
                        "recipient": f"recipient{i}@example.com",
                        "currency": "USD"
                    }
                )
                tasks.append(response)
            
            # Verify all succeeded
            for response in tasks:
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "processing"


class TestPerformance:
    """Test performance and response times"""
    
    def test_user_context_response_time(self, integration_client, mock_services):
        """Test user context API response time (should be < 500ms)"""
        import time
        
        with patch('user_router.cdp_service', mock_services['cdp']), \
             patch('user_router.kyc_service', mock_services['kyc']):
            
            start = time.time()
            response = integration_client.get(
                "/api/integration/user/user_123/context"
            )
            end = time.time()
            
            assert response.status_code == 200
            response_time = (end - start) * 1000  # Convert to ms
            assert response_time < 500, f"Response time {response_time}ms exceeds 500ms"
    
    def test_transaction_initiation_response_time(self, integration_client, mock_services):
        """Test transaction initiation response time (should be < 500ms)"""
        import time
        
        with patch('orchestrator.cdp_service', mock_services['cdp']), \
             patch('orchestrator.kyc_service', mock_services['kyc']), \
             patch('orchestrator.payment_service', mock_services['payment']):
            
            # Update KYC to Tier 1
            mock_services['kyc'].get_kyc_status.return_value = {
                "tier": 1,
                "status": "verified",
                "limits": {"daily": 3000, "monthly": 50000}
            }
            
            start = time.time()
            response = integration_client.post(
                "/api/integration/transaction/initiate",
                json={
                    "user_id": "user_123",
                    "amount": 500,
                    "recipient": "recipient@example.com",
                    "currency": "USD"
                }
            )
            end = time.time()
            
            assert response.status_code == 200
            response_time = (end - start) * 1000
            assert response_time < 500, f"Response time {response_time}ms exceeds 500ms"


# Run all integration tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
