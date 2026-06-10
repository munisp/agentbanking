import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
import asyncio
from typing import List, Dict, Any

# Assuming the classes are imported from the hypothetical implementation file
# In a real project, this would be: from your_project.orchestrator import GatewayOrchestrator, GatewayAdapter
# For this task, we'll import them directly from the design file content.
# We will use a mock class structure to avoid actual import issues in the sandbox.

class MockGatewayAdapter:
    """Mock implementation of GatewayAdapter for testing."""
    def __init__(self, name: str, priority: int):
        self.name = name
        self.priority = priority
        self.success_count = 0
        self.failure_count = 0
        self.last_successful_transaction = None
        self.last_failed_transaction = None
        self.consecutive_failures = 0
        self.process_transaction = AsyncMock()

    def get_stats(self) -> Dict[str, Any]:
        """Returns current performance statistics for the gateway."""
        return {
            "name": self.name,
            "priority": self.priority,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_successful_transaction": self.last_successful_transaction.isoformat() if self.last_successful_transaction else None,
            "last_failed_transaction": self.last_failed_transaction.isoformat() if self.last_failed_transaction else None,
            "failure_rate": self.failure_count / (self.success_count + self.failure_count) if (self.success_count + self.failure_count) > 0 else 0.0
        }

# We need the actual GatewayOrchestrator class structure to test its logic.
# We will copy the necessary parts of the design into the test file scope for self-containment.

class GatewayOrchestrator:
    """Manages multiple payment gateways, handling selection, processing, and failover."""

    def __init__(self, adapters: List[MockGatewayAdapter]):
        self.adapters: List[MockGatewayAdapter] = sorted(adapters, key=lambda x: x.priority)
        self.transaction_log: Dict[str, Dict[str, Any]] = {}
        self.failover_threshold = 3
        self.active_gateways: Dict[str, bool] = {adapter.name: True for adapter in self.adapters}

    def select_gateway(self, transaction_id: str) -> MockGatewayAdapter | None:
        """Selects the highest priority active gateway."""
        for adapter in self.adapters:
            if self.active_gateways.get(adapter.name, False):
                return adapter
        return None

    async def process_transaction(self, amount: float, currency: str, token: str, transaction_id: str) -> Dict[str, Any]:
        """Attempts to process a transaction using the selected gateway, with failover logic."""
        gateways_to_try = [adapter for adapter in self.adapters if self.active_gateways.get(adapter.name, False)]
        
        if not gateways_to_try:
            return {"status": "failed", "message": "No active gateways available."}

        result = None
        
        last_result = None
        
        for adapter in gateways_to_try:
            try:
                result = await adapter.process_transaction(amount, currency, token)
                last_result = result
                
                self._update_gateway_stats(adapter, success=result.get("status") == "success")
                self._log_transaction(transaction_id, adapter.name, result)
                
                if result.get("status") == "success":
                    return result
                
            except Exception as e:
                error_message = f"Gateway {adapter.name} failed with an unexpected error: {str(e)}"
                last_result = {"status": "error", "message": error_message, "gateway": adapter.name}
                self._update_gateway_stats(adapter, success=False)
                self._log_transaction(transaction_id, adapter.name, last_result)
                
        # If the loop finishes without a successful transaction, return the last result if it exists,
        # otherwise return a consolidated failure message.
        return last_result if last_result else {"status": "failed", "message": "All active gateways failed to process the transaction."}

    def _update_gateway_stats(self, adapter: MockGatewayAdapter, success: bool):
        """Internal method to update stats and apply failover logic."""
        
        adapter_instance = next((a for a in self.adapters if a.name == adapter.name), None)
        if not adapter_instance:
            return

        if success:
            adapter_instance.success_count += 1
            adapter_instance.last_successful_transaction = datetime.now()
            adapter_instance.consecutive_failures = 0
            self.active_gateways[adapter_instance.name] = True
        else:
            adapter_instance.failure_count += 1
            adapter_instance.last_failed_transaction = datetime.now()
            
            adapter_instance.consecutive_failures += 1
            
            if adapter_instance.consecutive_failures >= self.failover_threshold:
                self.active_gateways[adapter_instance.name] = False

    def _log_transaction(self, transaction_id: str, gateway_name: str, result: Dict[str, Any]):
        """Logs the transaction attempt."""
        if transaction_id not in self.transaction_log:
            self.transaction_log[transaction_id] = {"attempts": []}
        
        self.transaction_log[transaction_id]["attempts"].append({
            "timestamp": datetime.now().isoformat(),
            "gateway": gateway_name,
            "result": result
        })

    def get_transaction_tracking(self, transaction_id: str) -> Dict[str, Any] | None:
        """Retrieves the full log for a specific transaction."""
        return self.transaction_log.get(transaction_id)

    def get_gateway_stats(self) -> List[Dict[str, Any]]:
        """Retrieves statistics for all gateways."""
        return [adapter.get_stats() for adapter in self.adapters]

    def reactivate_gateway(self, gateway_name: str):
        """Manually reactivates a deactivated gateway."""
        if gateway_name in self.active_gateways:
            self.active_gateways[gateway_name] = True
            adapter_instance = next((a for a in self.adapters if a.name == gateway_name), None)
            if adapter_instance:
                adapter_instance.consecutive_failures = 0
        
    def deactivate_gateway(self, gateway_name: str):
        """Manually deactivates an active gateway."""
        if gateway_name in self.active_gateways:
            self.active_gateways[gateway_name] = False


# --- Pytest Fixtures ---

@pytest.fixture
def mock_adapters() -> List[MockGatewayAdapter]:
    """Fixture for four mock gateway adapters with different priorities."""
    adapters = [
        MockGatewayAdapter(name="GatewayA", priority=1), # Highest priority
        MockGatewayAdapter(name="GatewayB", priority=2),
        MockGatewayAdapter(name="GatewayC", priority=3),
        MockGatewayAdapter(name="GatewayD", priority=4), # Lowest priority
    ]
    return adapters

@pytest.fixture
def orchestrator(mock_adapters: List[MockGatewayAdapter]) -> GatewayOrchestrator:
    """Fixture for a fresh GatewayOrchestrator instance."""
    return GatewayOrchestrator(mock_adapters)

@pytest.fixture
def transaction_details() -> Dict[str, Any]:
    """Fixture for standard transaction details."""
    return {
        "amount": 100.00,
        "currency": "USD",
        "token": "test_token_123",
        "transaction_id": "txn_12345"
    }

# --- Test Cases ---

class TestGatewayOrchestrator:

    # --- Test select_gateway (all scenarios) ---

    def test_should_select_highest_priority_active_gateway(self, orchestrator: GatewayOrchestrator):
        """Test selection of the highest priority gateway when all are active."""
        selected = orchestrator.select_gateway("txn_test_1")
        assert selected is not None
        assert selected.name == "GatewayA"

    def test_should_select_next_highest_priority_when_highest_is_inactive(self, orchestrator: GatewayOrchestrator):
        """Test selection when the highest priority gateway is manually deactivated."""
        orchestrator.deactivate_gateway("GatewayA")
        selected = orchestrator.select_gateway("txn_test_2")
        assert selected is not None
        assert selected.name == "GatewayB"

    def test_should_return_none_when_no_active_gateways_exist(self, orchestrator: GatewayOrchestrator):
        """Test selection when all gateways are deactivated."""
        for adapter in orchestrator.adapters:
            orchestrator.deactivate_gateway(adapter.name)
        
        selected = orchestrator.select_gateway("txn_test_3")
        assert selected is None

    # --- Test process_transaction (all gateways) ---

    @pytest_asyncio.fixture(autouse=True)
    def setup_teardown(self, mock_adapters: List[MockGatewayAdapter]):
        """Setup: Reset mocks before each test."""
        for adapter in mock_adapters:
            adapter.process_transaction.reset_mock()
            adapter.process_transaction.side_effect = None
            adapter.consecutive_failures = 0
            adapter.success_count = 0
            adapter.failure_count = 0
            adapter.last_successful_transaction = None
            adapter.last_failed_transaction = None
        
        # Teardown is implicit, as fixtures create new objects

    @pytest.mark.asyncio
    async def test_should_process_successfully_with_highest_priority_gateway(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test successful transaction processing by the first (highest priority) gateway."""
        mock_adapters[0].process_transaction.return_value = {"status": "success", "gateway": "GatewayA", "ref": "ref_A"}
        
        result = await orchestrator.process_transaction(**transaction_details)
        
        assert result["status"] == "success"
        assert result["gateway"] == "GatewayA"
        mock_adapters[0].process_transaction.assert_called_once()
        mock_adapters[1].process_transaction.assert_not_called()
        
        # Check stats update
        stats = orchestrator.get_gateway_stats()
        assert next(s for s in stats if s['name'] == 'GatewayA')['success_count'] == 1
        assert next(s for s in stats if s['name'] == 'GatewayA')['failure_rate'] == 0.0

    @pytest.mark.asyncio
    async def test_should_failover_and_succeed_with_second_gateway(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test failover from the first failing gateway to the second successful gateway."""
        # GatewayA fails with a soft error (not an exception)
        mock_adapters[0].process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "soft_decline"}
        # GatewayB succeeds
        mock_adapters[1].process_transaction.return_value = {"status": "success", "gateway": "GatewayB", "ref": "ref_B"}
        
        result = await orchestrator.process_transaction(**transaction_details)
        
        assert result["status"] == "success"
        assert result["gateway"] == "GatewayB"
        mock_adapters[0].process_transaction.assert_called_once()
        mock_adapters[1].process_transaction.assert_called_once()
        mock_adapters[2].process_transaction.assert_not_called()

        # Check stats update
        stats = orchestrator.get_gateway_stats()
        assert next(s for s in stats if s['name'] == 'GatewayA')['failure_count'] == 1
        assert next(s for s in stats if s['name'] == 'GatewayB')['success_count'] == 1

    @pytest.mark.asyncio
    async def test_should_failover_on_exception_and_succeed_with_second_gateway(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test failover when the first gateway raises an unexpected exception."""
        # GatewayA raises an exception (e.g., network error)
        mock_adapters[0].process_transaction.side_effect = ConnectionError("Network timeout")
        # GatewayB succeeds
        mock_adapters[1].process_transaction.return_value = {"status": "success", "gateway": "GatewayB", "ref": "ref_B"}
        
        result = await orchestrator.process_transaction(**transaction_details)
        
        assert result["status"] == "success"
        assert result["gateway"] == "GatewayB"
        mock_adapters[0].process_transaction.assert_called_once()
        mock_adapters[1].process_transaction.assert_called_once()
        
        # Check transaction log for both attempts
        log = orchestrator.get_transaction_tracking(transaction_details["transaction_id"])
        assert len(log["attempts"]) == 2
        assert log["attempts"][0]["gateway"] == "GatewayA"
        assert log["attempts"][0]["result"]["status"] == "error"
        assert log["attempts"][1]["gateway"] == "GatewayB"
        assert log["attempts"][1]["result"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_should_fail_when_all_gateways_fail(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test scenario where all gateways fail to process the transaction."""
        for adapter in mock_adapters:
            adapter.process_transaction.return_value = {"status": "failed", "gateway": adapter.name, "reason": "hard_decline"}
        
        result = await orchestrator.process_transaction(**transaction_details)
        
        assert result["status"] == "failed"
        # The final result is the last gateway's failure result, which is a soft decline
        assert result["gateway"] == "GatewayD"
        assert result["reason"] == "hard_decline"
        for adapter in mock_adapters:
            adapter.process_transaction.assert_called_once()
        
        # Check stats update
        stats = orchestrator.get_gateway_stats()
        for s in stats:
            assert s['failure_count'] == 1
            assert s['failure_rate'] == 1.0

    @pytest.mark.asyncio
    async def test_should_fail_when_no_active_gateways_are_available(self, orchestrator: GatewayOrchestrator, transaction_details: Dict[str, Any]):
        """Test scenario where the orchestrator has no active gateways to try."""
        for adapter in orchestrator.adapters:
            orchestrator.deactivate_gateway(adapter.name)
        
        result = await orchestrator.process_transaction(**transaction_details)
        
        assert result["status"] == "failed"
        assert "No active gateways available" in result["message"]

    # --- Test failover logic ---

    @pytest.mark.asyncio
    async def test_should_deactivate_gateway_after_failover_threshold_is_reached(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test that a gateway is deactivated after reaching the consecutive failure threshold (3)."""
        gateway_a = mock_adapters[0]
        gateway_a.process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "temp_error"}
        
        # Fail 3 times
        for i in range(1, 4):
            await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], f"txn_fail_{i}")
            assert orchestrator.active_gateways["GatewayA"] == (i < orchestrator.failover_threshold)
            assert gateway_a.consecutive_failures == i

        # GatewayA should now be inactive
        assert orchestrator.active_gateways["GatewayA"] is False
        
        # Next transaction should skip GatewayA and select GatewayB
        # GatewayB is the next in line and should succeed
        mock_adapters[1].process_transaction.return_value = {"status": "success", "gateway": "GatewayB", "ref": "ref_B"}
        
        # The 4th transaction should be processed by GatewayB and succeed
        result = await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_fail_4")
        
        assert result["status"] == "success"
        assert result["gateway"] == "GatewayB"
        assert gateway_a.process_transaction.call_count == 3 # Only called 3 times
        mock_adapters[1].process_transaction.assert_called_once() # Called once for the 4th transaction

    @pytest.mark.asyncio
    async def test_should_reset_consecutive_failures_on_success(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test that a single success resets the consecutive failure count."""
        gateway_a = mock_adapters[0]
        
        # 1. Fail twice
        gateway_a.process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "temp_error"}
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_fail_1")
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_fail_2")
        assert gateway_a.consecutive_failures == 2
        assert orchestrator.active_gateways["GatewayA"] is True

        # 2. Succeed once
        gateway_a.process_transaction.return_value = {"status": "success", "gateway": "GatewayA", "ref": "ref_A"}
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_success_1")
        assert gateway_a.consecutive_failures == 0
        assert orchestrator.active_gateways["GatewayA"] is True
        
        # 3. Fail again (count should start from 1)
        gateway_a.process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "temp_error"}
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_fail_3")
        assert gateway_a.consecutive_failures == 1

    def test_should_reactivate_gateway_manually(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter]):
        """Test manual reactivation of a gateway."""
        gateway_a = mock_adapters[0]
        
        # Deactivate
        orchestrator.deactivate_gateway("GatewayA")
        assert orchestrator.active_gateways["GatewayA"] is False
        
        # Reactivate
        orchestrator.reactivate_gateway("GatewayA")
        assert orchestrator.active_gateways["GatewayA"] is True
        assert gateway_a.consecutive_failures == 0 # Should reset failures

    # --- Test transaction tracking ---

    @pytest.mark.asyncio
    async def test_should_track_single_successful_transaction(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test tracking for a transaction processed by a single gateway."""
        mock_adapters[0].process_transaction.return_value = {"status": "success", "gateway": "GatewayA", "ref": "ref_A"}
        await orchestrator.process_transaction(**transaction_details)
        
        log = orchestrator.get_transaction_tracking(transaction_details["transaction_id"])
        assert log is not None
        assert len(log["attempts"]) == 1
        assert log["attempts"][0]["gateway"] == "GatewayA"
        assert log["attempts"][0]["result"]["status"] == "success"
        assert "timestamp" in log["attempts"][0]

    @pytest.mark.asyncio
    async def test_should_track_failover_transaction_with_multiple_attempts(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test tracking for a transaction that fails over multiple gateways before success."""
        mock_adapters[0].process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "soft_decline"}
        mock_adapters[1].process_transaction.side_effect = ConnectionError("Timeout")
        mock_adapters[2].process_transaction.return_value = {"status": "success", "gateway": "GatewayC", "ref": "ref_C"}
        
        await orchestrator.process_transaction(**transaction_details)
        
        log = orchestrator.get_transaction_tracking(transaction_details["transaction_id"])
        assert log is not None
        assert len(log["attempts"]) == 3
        
        # Attempt 1: Soft failure
        assert log["attempts"][0]["gateway"] == "GatewayA"
        assert log["attempts"][0]["result"]["status"] == "failed"
        
        # Attempt 2: Exception/Error failure
        assert log["attempts"][1]["gateway"] == "GatewayB"
        assert log["attempts"][1]["result"]["status"] == "error"
        assert "Timeout" in log["attempts"][1]["result"]["message"]
        
        # Attempt 3: Success
        assert log["attempts"][2]["gateway"] == "GatewayC"
        assert log["attempts"][2]["result"]["status"] == "success"

    def test_should_return_none_for_untracked_transaction_id(self, orchestrator: GatewayOrchestrator):
        """Test retrieving tracking for a transaction ID that was never processed."""
        log = orchestrator.get_transaction_tracking("non_existent_txn")
        assert log is None

    # --- Test get_gateway_stats ---

    @pytest.mark.asyncio
    async def test_should_return_correct_initial_gateway_stats(self, orchestrator: GatewayOrchestrator):
        """Test initial stats before any transactions."""
        stats = orchestrator.get_gateway_stats()
        assert len(stats) == 4
        for stat in stats:
            assert stat["success_count"] == 0
            assert stat["failure_count"] == 0
            assert stat["failure_rate"] == 0.0
            assert stat["last_successful_transaction"] is None

    @pytest.mark.asyncio
    async def test_should_return_correct_updated_gateway_stats(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test stats after a mix of successful and failed transactions."""
        # GatewayA: 2 Success, 1 Soft Fail
        mock_adapters[0].process_transaction.side_effect = [
            {"status": "success", "gateway": "GatewayA", "ref": "ref_1"},
            {"status": "failed", "gateway": "GatewayA", "reason": "soft_decline"},
            {"status": "success", "gateway": "GatewayA", "ref": "ref_3"},
        ]
        # GatewayB: 1 Exception Fail, 1 Success (via failover)
        mock_adapters[1].process_transaction.side_effect = [
            ConnectionError("Timeout"),
            {"status": "success", "gateway": "GatewayB", "ref": "ref_4"},
        ]
        # GatewayC: 1 Soft Fail (via failover)
        mock_adapters[2].process_transaction.return_value = {"status": "failed", "gateway": "GatewayC", "reason": "soft_decline"}
        
        # Txn 1: A success
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_1")
        # Txn 2: A fail -> B exception -> C fail -> D success (need to set D)
        mock_adapters[3].process_transaction.return_value = {"status": "success", "gateway": "GatewayD", "ref": "ref_5"}
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_2")
        # Txn 3: A success
        await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_3")
        
        stats = orchestrator.get_gateway_stats()
        
        stats_a = next(s for s in stats if s['name'] == 'GatewayA')
        assert stats_a['success_count'] == 2
        assert stats_a['failure_count'] == 1
        assert stats_a['failure_rate'] == pytest.approx(1/3)
        assert stats_a['last_successful_transaction'] is not None
        assert stats_a['last_failed_transaction'] is not None

        stats_b = next(s for s in stats if s['name'] == 'GatewayB')
        assert stats_b['success_count'] == 0
        assert stats_b['failure_count'] == 1 # The exception counts as a failure
        assert stats_b['failure_rate'] == 1.0
        
        stats_c = next(s for s in stats if s['name'] == 'GatewayC')
        assert stats_c['success_count'] == 0
        assert stats_c['failure_count'] == 1
        assert stats_c['failure_rate'] == 1.0

        stats_d = next(s for s in stats if s['name'] == 'GatewayD')
        assert stats_d['success_count'] == 1
        assert stats_d['failure_count'] == 0
        assert stats_d['failure_rate'] == 0.0

    # --- Edge Case Testing ---

    @pytest.mark.asyncio
    async def test_edge_case_failover_with_only_one_gateway(self, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test failover logic when only one gateway is configured."""
        single_adapter = mock_adapters[0]
        orchestrator = GatewayOrchestrator([single_adapter])
        single_adapter.process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "temp_error"}
        
        # Fail 3 times
        for i in range(1, 4):
            await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], f"txn_fail_{i}")
        
        # GatewayA should be inactive
        assert orchestrator.active_gateways["GatewayA"] is False
        
        # Next transaction should fail immediately with "No active gateways available"
        result = await orchestrator.process_transaction(transaction_details["amount"], transaction_details["currency"], transaction_details["token"], "txn_fail_4")
        assert result["status"] == "failed"
        assert "No active gateways available" in result["message"]
        assert single_adapter.process_transaction.call_count == 3 # Only called 3 times

    @pytest.mark.asyncio
    async def test_edge_case_gateway_returns_error_status_but_no_exception(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test a gateway that returns a non-success status but is not an exception (should still trigger failover)."""
        mock_adapters[0].process_transaction.return_value = {"status": "error", "gateway": "GatewayA", "reason": "internal_error"}
        mock_adapters[1].process_transaction.return_value = {"status": "success", "gateway": "GatewayB", "ref": "ref_B"}
        
        result = await orchestrator.process_transaction(**transaction_details)
        
        assert result["status"] == "success"
        assert result["gateway"] == "GatewayB"
        mock_adapters[0].process_transaction.assert_called_once()
        mock_adapters[1].process_transaction.assert_called_once()
        
        # Check stats: GatewayA should have 1 failure
        stats = orchestrator.get_gateway_stats()
        assert next(s for s in stats if s['name'] == 'GatewayA')['failure_count'] == 1
        
    @pytest.mark.asyncio
    async def test_edge_case_transaction_id_collision(self, orchestrator: GatewayOrchestrator, mock_adapters: List[MockGatewayAdapter], transaction_details: Dict[str, Any]):
        """Test that using the same transaction ID multiple times logs all attempts correctly."""
        txn_id = "COLLISION_TXN"
        details_1 = transaction_details.copy()
        details_1["transaction_id"] = txn_id
        details_2 = transaction_details.copy()
        details_2["transaction_id"] = txn_id
        
        # Txn 1: A fails, B succeeds
        mock_adapters[0].process_transaction.return_value = {"status": "failed", "gateway": "GatewayA", "reason": "soft_decline"}
        mock_adapters[1].process_transaction.return_value = {"status": "success", "gateway": "GatewayB", "ref": "ref_B"}
        await orchestrator.process_transaction(**details_1)
        
        # Txn 2 (same ID): A succeeds
        mock_adapters[0].process_transaction.return_value = {"status": "success", "gateway": "GatewayA", "ref": "ref_A_2"}
        await orchestrator.process_transaction(**details_2)
        
        # The log should only contain the attempts from the *last* call to process_transaction
        # NOTE: The current implementation of _log_transaction *appends* to the list, which is a design choice.
        # If the requirement was to track *separate* transactions with the same ID, the ID should be unique.
        # Assuming the current design means all attempts for a given ID are logged sequentially.
        log = orchestrator.get_transaction_tracking(txn_id)
        assert len(log["attempts"]) == 3 # A fail, B success (from txn 1) + A success (from txn 2)
        
        # The log shows the sequence of attempts across all calls using that ID
        assert log["attempts"][0]["gateway"] == "GatewayA"
        assert log["attempts"][1]["gateway"] == "GatewayB"
        assert log["attempts"][2]["gateway"] == "GatewayA"
        assert log["attempts"][2]["result"]["status"] == "success"