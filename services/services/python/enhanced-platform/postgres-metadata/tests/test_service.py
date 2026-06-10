#!/usr/bin/env python3
"""
Test PostgreSQL Metadata Service
"""


import requests
import json

def test_service():
    base_url = "http://localhost:5433"
    
    print("🧪 Testing PostgreSQL Metadata Service...")
    
    # Test health check
    try:
        response = requests.get(f"{base_url}/health")
        data = response.json()
        
        assert data["role"] == "METADATA_ONLY_STORAGE"
        assert data["financial_data_location"] == "TIGERBEETLE_PRIMARY_LEDGER"
        print("✅ Health check passed")
        
        # Test PIX key resolution
        response = requests.get(f"{base_url}/api/v1/pix-keys/test@example.com")
        data = response.json()
        
        assert "tigerbeetle_account_id" in data
        assert "For account balance, query TigerBeetle" in data["note"]
        print("✅ PIX key resolution passed")
        
        print("🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_service()
    exit(0 if success else 1)
