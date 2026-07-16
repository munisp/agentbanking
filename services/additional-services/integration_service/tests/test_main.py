import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import time

# We need to import the create_app function and the external_service instance
# from the main module to properly mock and test.
# Since we are in the same directory, a simple import works.
from main import create_app, external_service

# --- Fixtures ---

@pytest.fixture(scope="module")
def mock_external_service():
    """
    Fixture to mock the ExternalService class methods for isolation.
    We use a patcher for the entire module scope.
    """
    with patch("main.ExternalService", autospec=True) as MockService:
        # Configure the mock instance that will be used inside create_app
        mock_instance = MockService.return_value
        mock_instance.connect = AsyncMock()
        mock_instance.disconnect = AsyncMock()
        mock_instance.is_connected = True # Default state for most tests

        # We need to ensure the global 'external_service' in main.py is the mock
        # For this simple case, we'll patch the instance directly in the module
        with patch("main.external_service", mock_instance):
            yield mock_instance

@pytest.fixture(scope="module")
def client(mock_external_service):
    """
    Fixture for the TestClient, which handles the application's lifespan events.
    It uses the mocked external service.
    """
    app = create_app()
    with TestClient(app) as client:
        yield client

# --- Test Cases ---

# 1. Application Initialization and Metadata Tests
def test_should_return_app_metadata_when_accessing_openapi_schema(client):
    """Test application metadata from the OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "TestApp"
    assert data["info"]["version"] == "1.0.0"
    assert data["info"]["description"] == "A test application for unit testing demonstration."

def test_should_return_welcome_message_when_accessing_root(client):
    """Test the basic root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the TestApp"}

# 2. Middleware Tests
def test_should_include_process_time_header_when_request_is_processed(client):
    """Test the custom_middleware adds the X-Process-Time header."""
    response = client.get("/")
    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    # Check if the value is a float string
    try:
        float(response.headers["X-Process-Time"])
    except ValueError:
        pytest.fail("X-Process-Time header is not a valid float string")

# 3. CORS Middleware Tests
@pytest.mark.parametrize("origin", [
    "http://localhost",
    "http://localhost:8080",
])
def test_should_allow_configured_origins_when_cors_is_enabled(client, origin):
    """Test that configured origins are allowed by CORS middleware."""
    response = client.get("/", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert response.headers["Access-Control-Allow-Credentials"] == "true"

def test_should_not_allow_unconfigured_origin_when_cors_is_enabled(client):
    """Test that an unconfigured origin is not allowed by CORS middleware."""
    unconfigured_origin = "http://evil.com"
    response = client.get("/", headers={"Origin": unconfigured_origin})
    assert response.status_code == 200 # FastAPI/Starlette allows the request to pass
    assert "Access-Control-Allow-Origin" not in response.headers

# 4. Router and Endpoint Tests
def test_should_return_item_details_when_reading_valid_item(client):
    """Test successful GET request to a router endpoint."""
    item_id = 123
    response = client.get(f"/api/v1/items/{item_id}")
    assert response.status_code == 200
    assert response.json() == {"item_id": item_id, "name": f"Item {item_id}"}

def test_should_return_404_when_reading_non_existent_item(client):
    """Test error scenario for GET request to a router endpoint."""
    item_id = 404
    response = client.get(f"/api/v1/items/{item_id}")
    assert response.status_code == 404
    assert response.json() == {"message": "Item not found"}

def test_should_return_success_message_when_creating_valid_item(client):
    """Test successful POST request to a router endpoint."""
    new_item = {"name": "Test Item", "price": 9.99}
    response = client.post("/api/v1/items/", json=new_item)
    assert response.status_code == 200
    assert response.json()["message"] == "Item created"
    assert response.json()["item"] == new_item

def test_should_return_400_when_creating_invalid_item(client):
    """Test error scenario for POST request to a router endpoint."""
    invalid_item = {"error": "Missing field"}
    response = client.post("/api/v1/items/", json=invalid_item)
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid item data"}

# 5. Health Check Endpoint Tests
def test_should_return_200_ok_when_external_service_is_connected(client, mock_external_service):
    """Test health check success scenario."""
    # Ensure the mock is set to connected state
    mock_external_service.is_connected = True
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "connected"}

def test_should_return_503_unavailable_when_external_service_is_disconnected(client, mock_external_service):
    """Test health check failure scenario."""
    # Temporarily set the mock to disconnected state
    mock_external_service.is_connected = False
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "service": "disconnected"}
    # Reset state for other tests
    mock_external_service.is_connected = True

# 6. Lifespan (Startup/Shutdown) Event Tests
def test_should_call_connect_on_startup_and_disconnect_on_shutdown(mock_external_service):
    """
    Test that the lifespan events correctly call the external service's
    connect and disconnect methods. The client fixture's scope="module"
    ensures the app is created and torn down once per module.
    """
    # The client fixture has already been created and torn down by the time
    # this test runs (due to scope="module" and the way TestClient works).
    # We just need to check the call counts on the mock.

    # connect is called once when the TestClient is initialized (startup)
    mock_external_service.connect.assert_called_once()

    # disconnect is called once when the TestClient context manager exits (shutdown)
    mock_external_service.disconnect.assert_called_once()

# 7. Edge Case Testing (Item ID type validation)
def test_should_return_422_unprocessable_entity_when_item_id_is_invalid_type(client):
    """Test FastAPI's automatic Pydantic validation for path parameters."""
    response = client.get("/api/v1/items/not_an_int")
    assert response.status_code == 422
    assert "detail" in response.json()
    assert response.json()["detail"][0]["loc"] == ["path", "item_id"]
    assert response.json()["detail"][0]["type"] == "int_parsing"

# 8. Edge Case Testing (Empty POST body)
def test_should_return_422_unprocessable_entity_when_post_body_is_empty(client):
    """Test FastAPI's automatic Pydantic validation for request body (if a model was used).
    Since the endpoint uses `item: dict`, it expects a JSON body. An empty body is invalid JSON.
    """
    response = client.post("/api/v1/items/", data="")
    assert response.status_code == 422
    assert "detail" in response.json()
    assert response.json()["detail"][0]["type"] == "json_invalid"

# 9. Edge Case Testing (Root endpoint with unallowed method)
def test_should_return_405_method_not_allowed_when_using_unallowed_method(client):
    """Test that only allowed methods are accepted for an endpoint."""
    response = client.post("/")
    assert response.status_code == 405
    assert response.json()["detail"] == "Method Not Allowed"

# 10. Test Router Prefix
def test_should_not_find_endpoint_without_prefix(client):
    """Test that endpoints are correctly registered under the prefix."""
    response = client.get("/items/1")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"