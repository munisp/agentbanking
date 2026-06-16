"""
Pytest configuration and shared fixtures for CDP service tests
"""

import pytest
import asyncio
from typing import AsyncGenerator
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import app components
import sys
sys.path.insert(0, '/home/ubuntu/NIGERIAN_REMITTANCE_100_PARITY/backend/cdp-service')

from app.core.database import Base, get_db
from app.core.config import settings
from app.main import app

# Test database URL
TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/cdp_service"

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def test_db():
    """Create test database"""
    engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
    )
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield
    
    # Drop tables
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def client(test_db) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for testing"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_cdp_service(monkeypatch):
    """Mock CDP service for testing without actual CDP calls"""
    
    class MockCDPService:
        async def create_wallet(self, email: str):
            return {
                "wallet_address": f"0x{email[:40].ljust(40, '0')}",
                "wallet_id": f"wallet_{email}"
            }
        
        async def get_balance(self, wallet_address: str):
            return [
                {"token": "ETH", "balance": "1.5", "usd_value": "3000.00"},
                {"token": "USDC", "balance": "1000.0", "usd_value": "1000.00"},
                {"token": "USDT", "balance": "500.0", "usd_value": "500.00"}
            ]
        
        async def get_transactions(self, wallet_address: str):
            return [
                {
                    "hash": "0x123...",
                    "from": wallet_address,
                    "to": "0x456...",
                    "value": "0.1",
                    "token": "ETH",
                    "timestamp": "2024-11-05T10:00:00Z"
                }
            ]
        
        async def estimate_gas(self, from_address: str, to_address: str, amount: str, token: str):
            return {
                "gas_limit": "21000",
                "gas_price": "20",
                "estimated_cost": "0.00042"
            }
        
        async def create_escrow(self, sender: str, recipient_email: str, amount: str, token: str):
            return {
                "escrow_id": "escrow_123",
                "transaction_hash": "0xabc...",
                "status": "pending"
            }
        
        async def claim_escrow(self, escrow_id: str, recipient_address: str):
            return {
                "transaction_hash": "0xdef...",
                "status": "completed"
            }
        
        async def refund_escrow(self, escrow_id: str):
            return {
                "transaction_hash": "0xghi...",
                "status": "refunded"
            }
    
    from app.services import cdp_service
    monkeypatch.setattr(cdp_service, "CDPService", MockCDPService)
    return MockCDPService()

@pytest.fixture
def mock_otp_service(monkeypatch):
    """Mock OTP service for testing without sending actual emails"""
    
    class MockOTPService:
        def generate_otp(self) -> str:
            return "123456"
        
        async def send_otp_email(self, email: str, otp: str, purpose: str):
            return True
        
        def hash_otp(self, otp: str) -> str:
            return f"hashed_{otp}"
        
        def verify_otp_hash(self, otp: str, hashed: str) -> bool:
            return f"hashed_{otp}" == hashed
    
    from app.services import otp_service
    monkeypatch.setattr(otp_service, "OTPService", MockOTPService)
    return MockOTPService()

@pytest.fixture
async def authenticated_user(client: httpx.AsyncClient, mock_cdp_service, mock_otp_service):
    """Create and authenticate a test user"""
    
    email = "testuser@example.com"
    
    # Send OTP
    response = await client.post("/auth/cdp/send-otp", json={
        "email": email,
        "purpose": "signup"
    })
    assert response.status_code == 200
    
    # Verify OTP
    response = await client.post("/auth/cdp/verify-otp", json={
        "email": email,
        "otp": "123456",
        "device_id": "test-device",
        "device_name": "Test Device",
        "device_type": "web"
    })
    assert response.status_code == 200
    
    data = response.json()
    return {
        "email": email,
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "wallet_address": data["user"]["wallet_address"],
        "user_id": data["user"]["id"]
    }

@pytest.fixture
def auth_headers(authenticated_user):
    """Get authorization headers for authenticated requests"""
    return {"Authorization": f"Bearer {authenticated_user['access_token']}"}

# Markers
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "security: Security tests")
