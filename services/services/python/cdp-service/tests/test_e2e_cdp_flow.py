"""
End-to-End CDP Flow Integration Tests
Tests complete user journeys from registration to transaction
"""

import pytest
import httpx
from datetime import datetime, timedelta
import asyncio

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
class TestE2ECDPFlow:
    """End-to-end tests for complete CDP flows"""
    
    async def test_complete_registration_to_transaction_flow(self):
        """Test complete flow: Register → Login → Create Escrow → Claim"""
        
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            # Step 1: Send OTP for registration
            response = await client.post("/auth/cdp/send-otp", json={
                "email": "newuser@example.com",
                "purpose": "signup"
            })
            assert response.status_code == 200
            assert response.json()["success"] is True
            
            # Step 2: Verify OTP and complete registration
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": "newuser@example.com",
                "otp": "123456",  # Mock OTP
                "device_id": "test-device-001",
                "device_name": "Test Device",
                "device_type": "web"
            })
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
            
            access_token = data["access_token"]
            wallet_address = data["user"]["wallet_address"]
            
            # Step 3: Get user profile
            response = await client.get(
                "/auth/cdp/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200
            user = response.json()
            assert user["email"] == "newuser@example.com"
            assert user["wallet_address"] == wallet_address
            
            # Step 4: Get wallet balance
            response = await client.get(
                "/wallet/balance",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200
            balances = response.json()
            assert isinstance(balances, list)
            
            # Step 5: Create escrow transaction
            response = await client.post(
                "/escrow/create",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "recipient_email": "recipient@example.com",
                    "amount": "0.01",
                    "token": "ETH",
                    "message": "Test payment"
                }
            )
            assert response.status_code == 200
            escrow = response.json()
            assert "escrow_id" in escrow
            assert escrow["status"] == "pending"
            
            escrow_id = escrow["escrow_id"]
            
            # Step 6: Get escrow details
            response = await client.get(
                f"/escrow/{escrow_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200
            details = response.json()
            assert details["escrow_id"] == escrow_id
            assert details["recipient_email"] == "recipient@example.com"
            
            # Step 7: Recipient claims escrow
            # First, recipient registers
            response = await client.post("/auth/cdp/send-otp", json={
                "email": "recipient@example.com",
                "purpose": "signup"
            })
            assert response.status_code == 200
            
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": "recipient@example.com",
                "otp": "123456",
                "device_id": "recipient-device-001"
            })
            assert response.status_code == 200
            recipient_token = response.json()["access_token"]
            
            # Recipient claims
            response = await client.post(
                "/escrow/claim",
                headers={"Authorization": f"Bearer {recipient_token}"},
                json={"escrow_id": escrow_id}
            )
            assert response.status_code == 200
            claim_result = response.json()
            assert claim_result["success"] is True
            
            # Step 8: Verify transaction history
            response = await client.get(
                "/wallet/transactions",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200
            transactions = response.json()
            assert len(transactions) > 0
    
    async def test_multi_device_login_flow(self):
        """Test user logging in from multiple devices"""
        
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            email = "multidevice@example.com"
            
            # Register user
            await client.post("/auth/cdp/send-otp", json={
                "email": email,
                "purpose": "signup"
            })
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": email,
                "otp": "123456",
                "device_id": "device-1"
            })
            token1 = response.json()["access_token"]
            
            # Login from device 2
            await client.post("/auth/cdp/send-otp", json={
                "email": email,
                "purpose": "login"
            })
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": email,
                "otp": "123456",
                "device_id": "device-2"
            })
            token2 = response.json()["access_token"]
            
            # Login from device 3
            await client.post("/auth/cdp/send-otp", json={
                "email": email,
                "purpose": "login"
            })
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": email,
                "otp": "123456",
                "device_id": "device-3"
            })
            token3 = response.json()["access_token"]
            
            # List devices
            response = await client.get(
                "/auth/cdp/devices",
                headers={"Authorization": f"Bearer {token1}"}
            )
            assert response.status_code == 200
            devices = response.json()
            assert len(devices) == 3
            
            # Revoke device 2
            device_2_id = [d for d in devices if d["device_id"] == "device-2"][0]["id"]
            response = await client.delete(
                f"/auth/cdp/devices/{device_2_id}",
                headers={"Authorization": f"Bearer {token1}"}
            )
            assert response.status_code == 200
            
            # Verify device 2 token is invalid
            response = await client.get(
                "/auth/cdp/me",
                headers={"Authorization": f"Bearer {token2}"}
            )
            assert response.status_code == 401
    
    async def test_token_refresh_flow(self):
        """Test token refresh flow"""
        
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            email = "refresh@example.com"
            
            # Register
            await client.post("/auth/cdp/send-otp", json={
                "email": email,
                "purpose": "signup"
            })
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": email,
                "otp": "123456"
            })
            
            access_token = response.json()["access_token"]
            refresh_token = response.json()["refresh_token"]
            
            # Use access token
            response = await client.get(
                "/auth/cdp/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            assert response.status_code == 200
            
            # Refresh token
            response = await client.post(
                "/auth/cdp/refresh",
                json={"refresh_token": refresh_token}
            )
            assert response.status_code == 200
            new_access_token = response.json()["access_token"]
            
            # Use new access token
            response = await client.get(
                "/auth/cdp/me",
                headers={"Authorization": f"Bearer {new_access_token}"}
            )
            assert response.status_code == 200
    
    async def test_escrow_expiry_and_refund_flow(self):
        """Test escrow expiry and refund flow"""
        
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            # Create user
            await client.post("/auth/cdp/send-otp", json={
                "email": "sender@example.com",
                "purpose": "signup"
            })
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": "sender@example.com",
                "otp": "123456"
            })
            token = response.json()["access_token"]
            
            # Create escrow
            response = await client.post(
                "/escrow/create",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "recipient_email": "unclaimed@example.com",
                    "amount": "0.01",
                    "token": "ETH"
                }
            )
            escrow_id = response.json()["escrow_id"]
            
            # Try to refund before expiry (should fail)
            response = await client.post(
                "/escrow/refund",
                headers={"Authorization": f"Bearer {token}"},
                json={"escrow_id": escrow_id}
            )
            assert response.status_code == 400
            
            # Simulate time passing (30 days)
            # In real test, you'd mock the time or wait
            # For now, we'll just verify the endpoint exists
            
            # After expiry, refund should succeed
            # response = await client.post(
            #     "/escrow/refund",
            #     headers={"Authorization": f"Bearer {token}"},
            #     json={"escrow_id": escrow_id}
            # )
            # assert response.status_code == 200
    
    async def test_concurrent_operations(self):
        """Test concurrent operations don't cause race conditions"""
        
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            # Register user
            await client.post("/auth/cdp/send-otp", json={
                "email": "concurrent@example.com",
                "purpose": "signup"
            })
            response = await client.post("/auth/cdp/verify-otp", json={
                "email": "concurrent@example.com",
                "otp": "123456"
            })
            token = response.json()["access_token"]
            
            # Make 10 concurrent requests to get balance
            tasks = [
                client.get(
                    "/wallet/balance",
                    headers={"Authorization": f"Bearer {token}"}
                )
                for _ in range(10)
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # All should succeed
            for response in responses:
                assert response.status_code == 200
                assert isinstance(response.json(), list)
