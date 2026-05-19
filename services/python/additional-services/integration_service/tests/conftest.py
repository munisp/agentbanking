"""Pytest configuration and shared fixtures"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
import asyncio

@pytest.fixture
def mock_cdp_service():
    """Mock CDP service"""
    mock = Mock()
    mock.get_wallet = AsyncMock(return_value={
        "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "balance": {"usdc": "1500.00", "ngn": "2250000.00"}
    })
    return mock

@pytest.fixture
def mock_kyc_service():
    """Mock KYC service"""
    mock = Mock()
    mock.get_kyc_status = AsyncMock(return_value={
        "tier": 1,
        "status": "verified",
        "limits": {"daily": 3000, "monthly": 50000}
    })
    return mock

@pytest.fixture
def mock_payment_service():
    """Mock Payment Gateway service"""
    mock = Mock()
    mock.process_payment = AsyncMock(return_value={
        "transaction_id": "txn_123",
        "status": "processing"
    })
    return mock

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = Mock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.publish = AsyncMock(return_value=1)
    return mock

@pytest.fixture
def sample_user_id():
    """Sample user ID for testing"""
    return "user_12345"

@pytest.fixture
def sample_transaction():
    """Sample transaction data"""
    return {
        "amount": 500,
        "recipient": "recipient@example.com",
        "currency": "USD"
    }

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
