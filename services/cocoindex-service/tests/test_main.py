import pytest
from httpx import AsyncClient
from main import app

@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_create_resource():
    """Test resource creation"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "name": "Test Resource",
            "description": "Test Description"
        }
        response = await client.post("/api/v1/resources", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == payload["name"]
        assert "id" in data

@pytest.mark.asyncio
async def test_get_resource():
    """Test resource retrieval"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/resources/1")
        assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_unauthorized_access():
    """Test unauthorized access"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/protected-resource")
        assert response.status_code == 401
