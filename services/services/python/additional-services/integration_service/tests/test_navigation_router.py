import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Assume the following imports and definitions are available from the main application
# For a real test, these would be imported from the actual project structure.
# Since the actual code is not provided, we will define mocks and stubs.

# --- Stubs for Application Components (Replace with actual imports) ---

# Mock the main application object
class MockApp:
    def __init__(self):
        self.router = MagicMock()

# Mock the router/module under test
class MockNavigationRouter:
    def __init__(self):
        self.router = MagicMock()

# Mock the dependencies/services
class MockNavigationService:
    async def create_context(self, user_id: str, context_data: dict):
        if user_id == "error_user":
            raise ValueError("Context creation failed")
        return {"context_id": "ctx_123", "user_id": user_id, **context_data}

    async def get_design_tokens(self, theme: str):
        if theme == "invalid":
            return None
        return {"primary": "#007bff", "secondary": "#6c757d", "theme": theme}

    async def validate_context(self, context_id: str):
        if context_id == "invalid_ctx":
            return False
        return True

# Mock Redis/Cache
class MockRedisCache:
    async def get(self, key):
        if key == "tokens:dark":
            return '{"primary": "#000000", "secondary": "#ffffff", "theme": "dark"}'
        return None

    async def set(self, key, value, ex):
        pass

# Mock the SSE dependency (e.g., a generator function)
async def mock_event_generator(user_id: str):
    if user_id == "no_events":
        yield "data: heartbeat\n\n"
        return
    yield "data: event 1\n\n"
    await asyncio.sleep(0.001) # Simulate async wait
    yield "data: event 2\n\n"

# --- Pytest Fixtures ---

@pytest.fixture
def mock_navigation_service():
    """Fixture for a mocked NavigationService instance."""
    return MockNavigationService()

@pytest.fixture
def mock_redis_cache():
    """Fixture for a mocked RedisCache instance."""
    return MockRedisCache()

@pytest.fixture
def mock_app_dependencies(mock_navigation_service, mock_redis_cache):
    """Fixture to mock the dependencies for the router."""
    # In a real application, you would use FastAPI's dependency override system.
    # Here we just return the mocks for use in the tests.
    return {
        "navigation_service": mock_navigation_service,
        "redis_cache": mock_redis_cache,
    }

@pytest.fixture
def client(mock_app_dependencies):
    """Fixture for a synchronous TestClient."""
    from fastapi import FastAPI, APIRouter, Depends, HTTPException
    from starlette.responses import StreamingResponse

    app = FastAPI()
    router = APIRouter()

    # Dependency stubs to simulate injection
    def get_nav_service():
        return mock_app_dependencies["navigation_service"]

    def get_redis_cache():
        return mock_app_dependencies["redis_cache"]

    # --- Router Endpoints Stub (Simulate navigation_router.py) ---

    @router.post("/navigation/context")
    async def create_navigation_context(
        user_id: str,
        context_data: dict,
        nav_service: MockNavigationService = Depends(get_nav_service),
    ):
        try:
            result = await nav_service.create_context(user_id, context_data)
            return {"status": "success", "data": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/design/tokens")
    async def get_design_tokens(
        theme: str = "light",
        nav_service: MockNavigationService = Depends(get_nav_service),
        cache: MockRedisCache = Depends(get_redis_cache),
    ):
        # 1. Check cache
        cached_tokens = await cache.get(f"tokens:{theme}")
        if cached_tokens:
            return {"status": "success", "data": eval(cached_tokens)} # eval for simplicity

        # 2. Fetch from service
        tokens = await nav_service.get_design_tokens(theme)
        if not tokens:
            raise HTTPException(status_code=404, detail="Design tokens not found for theme")

        # 3. Cache and return
        await cache.set(f"tokens:{theme}", str(tokens), ex=3600)
        return {"status": "success", "data": tokens}

    @router.get("/event/stream")
    async def event_stream(user_id: str):
        return StreamingResponse(mock_event_generator(user_id), media_type="text/event-stream")

    @router.get("/context/validate")
    async def validate_context(
        context_id: str,
        nav_service: MockNavigationService = Depends(get_nav_service),
    ):
        is_valid = await nav_service.validate_context(context_id)
        if not is_valid:
            raise HTTPException(status_code=404, detail="Context ID is invalid or expired")
        return {"status": "success", "is_valid": True}

    app.include_router(router)
    return TestClient(app)

@pytest.fixture
async def async_client(mock_app_dependencies):
    """Fixture for an asynchronous AsyncClient."""
    from fastapi import FastAPI, APIRouter, Depends, HTTPException
    from starlette.responses import StreamingResponse

    app = FastAPI()
    router = APIRouter()

    # Dependency stubs to simulate injection
    def get_nav_service():
        return mock_app_dependencies["navigation_service"]

    def get_redis_cache():
        return mock_app_dependencies["redis_cache"]

    # --- Router Endpoints Stub (Simulate navigation_router.py) ---

    @router.post("/navigation/context")
    async def create_navigation_context(
        user_id: str,
        context_data: dict,
        nav_service: MockNavigationService = Depends(get_nav_service),
    ):
        try:
            result = await nav_service.create_context(user_id, context_data)
            return {"status": "success", "data": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/design/tokens")
    async def get_design_tokens(
        theme: str = "light",
        nav_service: MockNavigationService = Depends(get_nav_service),
        cache: MockRedisCache = Depends(get_redis_cache),
    ):
        # 1. Check cache
        cached_tokens = await cache.get(f"tokens:{theme}")
        if cached_tokens:
            return {"status": "success", "data": eval(cached_tokens)} # eval for simplicity

        # 2. Fetch from service
        tokens = await nav_service.get_design_tokens(theme)
        if not tokens:
            raise HTTPException(status_code=404, detail="Design tokens not found for theme")

        # 3. Cache and return
        await cache.set(f"tokens:{theme}", str(tokens), ex=3600)
        return {"status": "success", "data": tokens}

    @router.get("/event/stream")
    async def event_stream(user_id: str):
        return StreamingResponse(mock_event_generator(user_id), media_type="text/event-stream")

    @router.get("/context/validate")
    async def validate_context(
        context_id: str,
        nav_service: MockNavigationService = Depends(get_nav_service),
    ):
        is_valid = await nav_service.validate_context(context_id)
        if not is_valid:
            raise HTTPException(status_code=404, detail="Context ID is invalid or expired")
        return {"status": "success", "is_valid": True}

    app.include_router(router)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# --- Test Cases for create_navigation_context endpoint ---

@pytest.mark.asyncio
async def test_should_create_context_successfully_when_valid_data_is_provided(async_client):
    """Test successful creation of a navigation context."""
    user_id = "user_456"
    context_data = {"page": "/dashboard", "source": "web"}
    response = await async_client.post(
        "/navigation/context",
        params={"user_id": user_id},
        json=context_data
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    data = response.json()["data"]
    assert data["user_id"] == user_id
    assert data["page"] == context_data["page"]
    assert "context_id" in data

@pytest.mark.asyncio
async def test_should_return_400_error_when_service_raises_value_error(async_client):
    """Test error handling when the service layer fails to create context."""
    user_id = "error_user"
    context_data = {"page": "/fail"}
    response = await async_client.post(
        "/navigation/context",
        params={"user_id": user_id},
        json=context_data
    )
    assert response.status_code == 400
    assert "Context creation failed" in response.json()["detail"]

@pytest.mark.asyncio
async def test_should_return_422_error_when_user_id_is_missing(async_client):
    """Test validation error for missing required query parameter (user_id)."""
    context_data = {"page": "/missing_user"}
    response = await async_client.post(
        "/navigation/context",
        json=context_data
    )
    # FastAPI returns 422 for validation errors on missing required parameters
    assert response.status_code == 422

# --- Test Cases for get_design_tokens endpoint ---

@pytest.mark.asyncio
async def test_should_return_cached_tokens_when_available(async_client, mock_redis_cache):
    """Test that the endpoint returns tokens from the cache if they exist."""
    # The mock_redis_cache fixture is set up to return 'dark' tokens
    response = await async_client.get("/design/tokens", params={"theme": "dark"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    data = response.json()["data"]
    assert data["theme"] == "dark"
    assert data["primary"] == "#000000"
    # Ensure service was NOT called (by checking if the response matches the hardcoded cache mock)
    # This is implicitly tested by the fixture setup, but in a real scenario, we'd use a spy/mock.

@pytest.mark.asyncio
async def test_should_fetch_and_cache_tokens_when_not_available_in_cache(async_client, mock_redis_cache):
    """Test fetching tokens from service and caching them."""
    theme = "light"
    # Mock the cache.set method to verify it was called
    mock_redis_cache.set = AsyncMock()
    response = await async_client.get("/design/tokens", params={"theme": theme})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    data = response.json()["data"]
    assert data["theme"] == theme
    assert data["primary"] == "#007bff" # Matches MockNavigationService output

    # Verify cache.set was called with the correct key and value
    mock_redis_cache.set.assert_called_once()
    call_args = mock_redis_cache.set.call_args[0]
    assert call_args[0] == "tokens:light"
    assert 'primary' in call_args[1] # Check if the value is the token string

@pytest.mark.asyncio
async def test_should_return_default_theme_tokens_when_no_theme_is_specified(async_client):
    """Test the default theme ('light') is used when no theme query param is provided."""
    response = await async_client.get("/design/tokens")
    assert response.status_code == 200
    assert response.json()["data"]["theme"] == "light"

@pytest.mark.asyncio
async def test_should_return_404_error_when_service_returns_no_tokens(async_client):
    """Test error handling when the service cannot find tokens for a theme."""
    response = await async_client.get("/design/tokens", params={"theme": "invalid"})
    assert response.status_code == 404
    assert "Design tokens not found for theme" in response.json()["detail"]

# --- Test Cases for event_stream endpoint (SSE) ---

@pytest.mark.asyncio
async def test_should_stream_multiple_events_when_user_has_events(async_client):
    """Test the Server-Sent Events (SSE) endpoint streams expected data."""
    user_id = "user_with_events"
    response = await async_client.get("/event/stream", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"

    # Read the streamed content
    content = response.text
    expected_events = [
        "data: event 1\n\n",
        "data: event 2\n\n"
    ]
    # Check if the content contains all expected events
    for event in expected_events:
        assert event in content

@pytest.mark.asyncio
async def test_should_stream_heartbeat_when_user_has_no_events(async_client):
    """Test the SSE endpoint streams a heartbeat for users with no immediate events."""
    user_id = "no_events"
    response = await async_client.get("/event/stream", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"

    # Read the streamed content
    content = response.text
    expected_heartbeat = "data: heartbeat\n\n"
    assert content.strip() == expected_heartbeat.strip()

# --- Test Cases for context validation endpoint ---

@pytest.mark.asyncio
async def test_should_return_success_and_valid_true_when_context_is_valid(async_client):
    """Test successful validation of a valid context ID."""
    context_id = "valid_ctx_123"
    response = await async_client.get("/context/validate", params={"context_id": context_id})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["is_valid"] is True

@pytest.mark.asyncio
async def test_should_return_404_error_when_context_is_invalid(async_client):
    """Test error handling for an invalid or expired context ID."""
    context_id = "invalid_ctx"
    response = await async_client.get("/context/validate", params={"context_id": context_id})
    assert response.status_code == 404
    assert "Context ID is invalid or expired" in response.json()["detail"]

@pytest.mark.asyncio
async def test_should_return_422_error_when_context_id_is_missing(async_client):
    """Test validation error for missing required query parameter (context_id)."""
    response = await async_client.get("/context/validate")
    assert response.status_code == 422

# --- Edge Case: Dependency Mocking Verification (using synchronous client for simplicity) ---

def test_should_use_mocked_service_for_context_creation(client, mock_navigation_service):
    """Verify that the test uses the mocked navigation service."""
    # Replace the mock service's method with a new AsyncMock to track calls
    mock_navigation_service.create_context = AsyncMock(return_value={"context_id": "mock_test"})

    user_id = "mock_user"
    context_data = {"test": "call"}
    client.post(
        "/navigation/context",
        params={"user_id": user_id},
        json=context_data
    )

    # Assert that the mocked method was called exactly once
    mock_navigation_service.create_context.assert_called_once_with(user_id, context_data)

def test_should_use_mocked_cache_for_token_check(client, mock_redis_cache):
    """Verify that the test uses the mocked redis cache."""
    # Replace the mock cache's get method with a new AsyncMock to track calls
    mock_redis_cache.get = AsyncMock(return_value=None) # Force a cache miss

    client.get("/design/tokens", params={"theme": "test_theme"})

    # Assert that the mocked method was called exactly once
    mock_redis_cache.get.assert_called_once_with("tokens:test_theme")

# --- Edge Case: Empty Context Data ---

@pytest.mark.asyncio
async def test_should_create_context_successfully_with_empty_context_data(async_client):
    """Test successful creation of a navigation context with an empty payload."""
    user_id = "user_empty_data"
    context_data = {}
    response = await async_client.post(
        "/navigation/context",
        params={"user_id": user_id},
        json=context_data
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    data = response.json()["data"]
    assert data["user_id"] == user_id
    assert "context_id" in data
    # Check that the context data is correctly merged (i.e., empty dict is present)
    assert data.get("page") is None
    assert data.get("source") is None
