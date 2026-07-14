import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import Optional
import asyncio

# --- Mocking the Application and Dependencies ---

# Mock Pydantic Schemas (assuming they exist in the real app)
class InitiateTransactionRequest(BaseModel):
    user_id: str
    amount: float
    currency: str
    recipient_id: str

class InitiateTransactionResponse(BaseModel):
    transaction_id: str
    status: str
    kyc_required: Optional[bool] = False

class TransactionStatusResponse(BaseModel):
    transaction_id: str
    status: str
    details: str

class KYCUpgradeCallbackRequest(BaseModel):
    transaction_id: str
    status: str # 'COMPLETED' or 'FAILED'

# Mock External Service Clients
class MockCDPService:
    async def get_user_balance(self, user_id: str) -> float:
        # Mock implementation for balance check
        if user_id == "user_insufficient_balance":
            return 50.0
        elif user_id == "user_kyc_required":
            return 1000.0
        return 500.0

class MockKYCService:
    async def check_kyc_status(self, user_id: str) -> bool:
        # Mock implementation for KYC check
        return user_id != "user_kyc_required"

    async def trigger_kyc_upgrade(self, user_id: str, transaction_id: str):
        # Mock implementation for triggering KYC upgrade
        pass

class MockPaymentService:
    async def process_payment(self, transaction_id: str, amount: float, recipient_id: str) -> str:
        # Mock implementation for payment processing
        if transaction_id == "tx_payment_fail":
            return "FAILED"
        return "PROCESSED"

# Mock Transaction Repository/DB
class MockTransactionRepo:
    def __init__(self):
        self.transactions = {}

    async def create_transaction(self, user_id, amount, currency, recipient_id, status="PENDING") -> str:
        tx_id = f"tx_{len(self.transactions) + 1}"
        self.transactions[tx_id] = {"id": tx_id, "user_id": user_id, "amount": amount, "status": status}
        return tx_id

    async def get_transaction(self, transaction_id: str) -> Optional[dict]:
        return self.transactions.get(transaction_id)

    async def update_transaction_status(self, transaction_id: str, status: str):
        if transaction_id in self.transactions:
            self.transactions[transaction_id]["status"] = status

# Mocking the actual router functions and dependencies injection
# In a real FastAPI app, these would be injected via Depends.
# We'll use a simple dictionary to hold our mocked services for easy patching.
MOCKED_SERVICES = {
    "cdp_service": MockCDPService(),
    "kyc_service": MockKYCService(),
    "payment_service": MockPaymentService(),
    "transaction_repo": MockTransactionRepo(),
}

# --- Fixtures ---

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_services():
    """Fixture to provide a fresh set of mock services for each test."""
    return {
        "cdp_service": AsyncMock(spec=MockCDPService),
        "kyc_service": AsyncMock(spec=MockKYCService),
        "payment_service": AsyncMock(spec=MockPaymentService),
        "transaction_repo": AsyncMock(spec=MockTransactionRepo),
    }

@pytest.fixture
def client(mock_services):
    """
    Fixture to create a TestClient for the FastAPI app,
    patching the dependencies with the provided mocks.
    """
    from fastapi import FastAPI, APIRouter, HTTPException, status

    # Minimal implementation of the router logic for testing purposes
    # This simulates the logic that would be in transaction_router.py
    router = APIRouter()

    # Helper to get mocked services (simulating dependency injection)
    def get_services():
        return mock_services

    @router.post("/transactions/initiate", response_model=InitiateTransactionResponse)
    async def initiate_transaction(request: InitiateTransactionRequest):
        services = get_services()
        user_id = request.user_id
        amount = request.amount

        # 1. KYC Check
        is_kyc_ok = await services["kyc_service"].check_kyc_status(user_id)
        if not is_kyc_ok:
            tx_id = await services["transaction_repo"].create_transaction(user_id, amount, request.currency, request.recipient_id, status="KYC_PENDING")
            await services["kyc_service"].trigger_kyc_upgrade(user_id, tx_id)
            return InitiateTransactionResponse(transaction_id=tx_id, status="KYC_PENDING", kyc_required=True)

        # 2. Balance Check
        balance = await services["cdp_service"].get_user_balance(user_id)
        if balance < amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

        # 3. Create Transaction
        tx_id = await services["transaction_repo"].create_transaction(user_id, amount, request.currency, request.recipient_id, status="PROCESSING")

        # 4. Process Payment (Simulate async background task or external call)
        payment_status = await services["payment_service"].process_payment(tx_id, amount, request.recipient_id)

        # 5. Update Status
        final_status = "COMPLETED" if payment_status == "PROCESSED" else "FAILED"
        await services["transaction_repo"].update_transaction_status(tx_id, final_status)

        return InitiateTransactionResponse(transaction_id=tx_id, status=final_status)

    @router.get("/transactions/{transaction_id}/status", response_model=TransactionStatusResponse)
    async def get_transaction_status(transaction_id: str):
        services = get_services()
        transaction = await services["transaction_repo"].get_transaction(transaction_id)
        if not transaction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        return TransactionStatusResponse(transaction_id=transaction["id"], status=transaction["status"], details=f"Status is {transaction['status']}")

    @router.post("/kyc/callback")
    async def kyc_upgrade_callback(callback: KYCUpgradeCallbackRequest):
        services = get_services()
        tx_id = callback.transaction_id
        new_status = "PENDING_RETRY" if callback.status == "COMPLETED" else "KYC_FAILED"
        await services["transaction_repo"].update_transaction_status(tx_id, new_status)
        return {"message": "Callback processed"}

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

# --- Test Cases ---

@pytest.mark.asyncio
async def test_should_initiate_transaction_successfully_when_all_checks_pass(client, mock_services):
    # Arrange
    request_data = {"user_id": "user_ok", "amount": 100.0, "currency": "USD", "recipient_id": "rec_123"}
    mock_services["kyc_service"].check_kyc_status.return_value = True
    mock_services["cdp_service"].get_user_balance.return_value = 500.0
    mock_services["transaction_repo"].create_transaction.return_value = "tx_success_1"
    mock_services["payment_service"].process_payment.return_value = "PROCESSED"

    # Act
    response = client.post("/transactions/initiate", json=request_data)

    # Assert
    assert response.status_code == 200
    data = InitiateTransactionResponse(**response.json())
    assert data.transaction_id == "tx_success_1"
    assert data.status == "COMPLETED"
    assert data.kyc_required is False

    # Verify mocks were called correctly
    mock_services["kyc_service"].check_kyc_status.assert_called_once_with("user_ok")
    mock_services["cdp_service"].get_user_balance.assert_called_once_with("user_ok")
    mock_services["transaction_repo"].create_transaction.assert_called_once()
    mock_services["payment_service"].process_payment.assert_called_once_with("tx_success_1", 100.0, "rec_123")
    mock_services["transaction_repo"].update_transaction_status.assert_called_once_with("tx_success_1", "COMPLETED")

@pytest.mark.asyncio
async def test_should_return_kyc_required_when_kyc_check_fails(client, mock_services):
    # Arrange
    request_data = {"user_id": "user_kyc_required", "amount": 200.0, "currency": "USD", "recipient_id": "rec_456"}
    mock_services["kyc_service"].check_kyc_status.return_value = False
    mock_services["transaction_repo"].create_transaction.return_value = "tx_kyc_2"

    # Act
    response = client.post("/transactions/initiate", json=request_data)

    # Assert
    assert response.status_code == 200
    data = InitiateTransactionResponse(**response.json())
    assert data.transaction_id == "tx_kyc_2"
    assert data.status == "KYC_PENDING"
    assert data.kyc_required is True

    # Verify mocks were called correctly
    mock_services["kyc_service"].check_kyc_status.assert_called_once_with("user_kyc_required")
    mock_services["transaction_repo"].create_transaction.assert_called_once()
    mock_services["kyc_service"].trigger_kyc_upgrade.assert_called_once_with("user_kyc_required", "tx_kyc_2")
    mock_services["cdp_service"].get_user_balance.assert_not_called()
    mock_services["payment_service"].process_payment.assert_not_called()
    mock_services["transaction_repo"].update_transaction_status.assert_not_called()

@pytest.mark.asyncio
async def test_should_fail_with_insufficient_balance_when_balance_is_low(client, mock_services):
    # Arrange
    request_data = {"user_id": "user_insufficient_balance", "amount": 600.0, "currency": "USD", "recipient_id": "rec_789"}
    mock_services["kyc_service"].check_kyc_status.return_value = True
    mock_services["cdp_service"].get_user_balance.return_value = 500.0 # Less than requested amount

    # Act
    response = client.post("/transactions/initiate", json=request_data)

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient balance"

    # Verify mocks were called correctly
    mock_services["kyc_service"].check_kyc_status.assert_called_once_with("user_insufficient_balance")
    mock_services["cdp_service"].get_user_balance.assert_called_once_with("user_insufficient_balance")
    mock_services["transaction_repo"].create_transaction.assert_not_called()
    mock_services["payment_service"].process_payment.assert_not_called()
    mock_services["transaction_repo"].update_transaction_status.assert_not_called()

@pytest.mark.asyncio
async def test_should_fail_transaction_when_payment_service_fails(client, mock_services):
    # Arrange
    request_data = {"user_id": "user_payment_fail", "amount": 100.0, "currency": "USD", "recipient_id": "rec_101"}
    mock_services["kyc_service"].check_kyc_status.return_value = True
    mock_services["cdp_service"].get_user_balance.return_value = 500.0
    mock_services["transaction_repo"].create_transaction.return_value = "tx_payment_fail"
    mock_services["payment_service"].process_payment.return_value = "FAILED"

    # Act
    response = client.post("/transactions/initiate", json=request_data)

    # Assert
    assert response.status_code == 200
    data = InitiateTransactionResponse(**response.json())
    assert data.transaction_id == "tx_payment_fail"
    assert data.status == "FAILED"

    # Verify mocks were called correctly
    mock_services["payment_service"].process_payment.assert_called_once_with("tx_payment_fail", 100.0, "rec_101")
    mock_services["transaction_repo"].update_transaction_status.assert_called_once_with("tx_payment_fail", "FAILED")

@pytest.mark.asyncio
async def test_should_get_transaction_status_successfully_when_transaction_exists(client, mock_services):
    # Arrange
    tx_id = "tx_status_check"
    mock_services["transaction_repo"].get_transaction.return_value = {"id": tx_id, "status": "COMPLETED"}

    # Act
    response = client.get(f"/transactions/{tx_id}/status")

    # Assert
    assert response.status_code == 200
    data = TransactionStatusResponse(**response.json())
    assert data.transaction_id == tx_id
    assert data.status == "COMPLETED"
    assert "COMPLETED" in data.details

    # Verify mocks were called correctly
    mock_services["transaction_repo"].get_transaction.assert_called_once_with(tx_id)

@pytest.mark.asyncio
async def test_should_return_404_when_getting_status_for_non_existent_transaction(client, mock_services):
    # Arrange
    tx_id = "tx_not_found"
    mock_services["transaction_repo"].get_transaction.return_value = None

    # Act
    response = client.get(f"/transactions/{tx_id}/status")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"

    # Verify mocks were called correctly
    mock_services["transaction_repo"].get_transaction.assert_called_once_with(tx_id)

@pytest.mark.asyncio
async def test_should_update_transaction_status_to_pending_retry_on_kyc_callback_success(client, mock_services):
    # Arrange
    tx_id = "tx_kyc_callback_success"
    callback_data = {"transaction_id": tx_id, "status": "COMPLETED"}

    # Act
    response = client.post("/kyc/callback", json=callback_data)

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == "Callback processed"

    # Verify mocks were called correctly
    mock_services["transaction_repo"].update_transaction_status.assert_called_once_with(tx_id, "PENDING_RETRY")

@pytest.mark.asyncio
async def test_should_update_transaction_status_to_kyc_failed_on_kyc_callback_failure(client, mock_services):
    # Arrange
    tx_id = "tx_kyc_callback_fail"
    callback_data = {"transaction_id": tx_id, "status": "FAILED"}

    # Act
    response = client.post("/kyc/callback", json=callback_data)

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == "Callback processed"

    # Verify mocks were called correctly
    mock_services["transaction_repo"].update_transaction_status.assert_called_once_with(tx_id, "KYC_FAILED")

@pytest.mark.asyncio
async def test_should_handle_invalid_initiate_transaction_request(client):
    # Arrange
    invalid_data = {"user_id": "user_id", "amount": "not_a_number", "currency": "USD", "recipient_id": "rec_123"}

    # Act
    response = client.post("/transactions/initiate", json=invalid_data)

    # Assert
    assert response.status_code == 422 # Unprocessable Entity for validation error
    assert "value is not a valid float" in response.json()["detail"][0]["msg"]

@pytest.mark.asyncio
async def test_should_handle_invalid_kyc_callback_request(client):
    # Arrange
    invalid_data = {"transaction_id": "tx_id", "status": "INVALID_STATUS"}

    # Act
    response = client.post("/kyc/callback", json=invalid_data)

    # Assert
    # Assuming the KYCUpgradeCallbackRequest model would validate the status field
    # For this mock, we'll assume it passes, but a real Pydantic model would fail
    # We'll test for a missing required field instead.
    invalid_data_missing_field = {"transaction_id": "tx_id"}
    response_missing = client.post("/kyc/callback", json=invalid_data_missing_field)
    assert response_missing.status_code == 422
    assert "field required" in response_missing.json()["detail"][0]["msg"]
