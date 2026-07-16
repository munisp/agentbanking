import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import date, timedelta
from kyc_checker import KYCChecker, KYCServiceError, TIER_LIMITS

# --- Fixtures for Mocked Dependencies ---

@pytest_asyncio.fixture
async def mock_db_client():
    """Fixture for a mocked database client."""
    client = MagicMock()
    client.fetch_user = AsyncMock()
    client.get_volume = AsyncMock()
    return client

@pytest.fixture
def mock_external_kyc_api():
    """Fixture for a mocked external KYC API client."""
    api = MagicMock()
    api.verify = AsyncMock()
    return api

@pytest.fixture
def kyc_checker_instance(mock_db_client, mock_external_kyc_api):
    """Fixture for the KYCChecker instance with mocked dependencies."""
    return KYCChecker(mock_db_client, mock_external_kyc_api)

# --- Fixtures for Test Data ---

@pytest.fixture
def user_id():
    return "test_user_123"

@pytest.fixture(autouse=True)
def patch_date_today(monkeypatch):
    """Fixture to patch datetime.date.today() for consistent testing."""
    class MockDate(date):
        @classmethod
        def today(cls):
            return date(2025, 10, 15) # A fixed date for testing
    monkeypatch.setattr("kyc_checker.datetime.date", MockDate)
    return MockDate.today()

# --- Test Suite for KYCChecker ---

class TestKYCChecker:

    # --- Test get_tier_limits method ---

    @pytest.mark.parametrize("tier, expected_limits", [
        (1, TIER_LIMITS[1]),
        (2, TIER_LIMITS[2]),
        (3, TIER_LIMITS[3]),
        (0, TIER_LIMITS[0]),
    ])
    def test_get_tier_limits_success(self, kyc_checker_instance, tier, expected_limits):
        """Test successful retrieval of limits for valid tiers."""
        limits = kyc_checker_instance.get_tier_limits(tier)
        assert limits == expected_limits

    def test_get_tier_limits_invalid_tier_raises_error(self, kyc_checker_instance):
        """Test that an invalid tier level raises a KYCServiceError."""
        with pytest.raises(KYCServiceError, match="Invalid KYC tier level: 99"):
            kyc_checker_instance.get_tier_limits(99)

    # --- Test calculate_required_tier method ---

    @pytest.mark.parametrize("amount, current_tier, expected_tier", [
        # Within current tier's max_transaction
        (500, 1, 1),
        (5000, 2, 2),
        (25000, 3, 3),
        # Requires upgrade
        (1001, 1, 2), # Tier 1 max is 1000, Tier 2 max is 5000
        (5001, 2, 3), # Tier 2 max is 5000, Tier 3 max is 25000
        # Edge case: Tier 0 user with a small transaction
        (10, 0, 1), # Tier 0 max is 0, so any amount > 0 requires Tier 1
        # Edge case: Amount greater than the highest tier's max_transaction
        (50000, 3, 3), # Capped at highest defined tier (3)
        (25001, 3, 3), # Capped at highest defined tier (3)
    ])
    def test_calculate_required_tier(self, kyc_checker_instance, amount, current_tier, expected_tier):
        """Test calculation of the minimum required KYC tier."""
        required_tier = kyc_checker_instance.calculate_required_tier(amount, current_tier)
        assert required_tier == expected_tier

    # --- Test check_kyc_requirements method ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tier, daily_vol, monthly_vol, amount, expected_result", [
        # Tier 1 Success: Well within all limits
        (1, 100, 500, 100, True), # Daily limit 1000, Monthly 5000, Max Tx 1000
        # Tier 2 Success: At the edge of limits
        (2, 9999, 49999, 1, True), # Daily limit 10000, Monthly 50000, Max Tx 5000
        # Tier 3 Success: Max single transaction
        (3, 1000, 1000, 25000, True), # Daily limit 100000, Monthly 500000, Max Tx 25000
        # Tier 0 Edge Case: Should fail because max_transaction is 0
        (0, 0, 0, 1, False), # Max Tx 0, requires Tier 1
        # Tier 1 Failure: Exceeds daily limit
        (1, 950, 500, 100, False), # 950 + 100 = 1050 > 1000
        # Tier 2 Failure: Exceeds monthly limit
        (2, 100, 49900, 200, False), # 49900 + 200 = 50100 > 50000
        # Tier 1 Failure: Exceeds max single transaction (1000) and requires upgrade (Tier 2)
        (1, 100, 500, 1001, False), # Requires Tier 2, but user is Tier 1
    ])
    async def test_check_kyc_requirements_limits(self, kyc_checker_instance, mock_db_client, user_id, tier, daily_vol, monthly_vol, amount, expected_result):
        """Test various limit and tier requirement scenarios for check_kyc_requirements."""
        # Setup mock user data
        mock_db_client.fetch_user.return_value = {"kyc_tier": tier}

        # Setup mock transaction volume history
        # Daily volume mock
        mock_db_client.get_volume.side_effect = [
            daily_vol,  # First call for daily volume
            monthly_vol # Second call for monthly volume
        ]

        result = await kyc_checker_instance.check_kyc_requirements(user_id, amount)
        assert result == expected_result

        # Assertions for mock calls
        mock_db_client.fetch_user.assert_called_once_with(user_id)
        
        # Check daily volume call
        today = date(2025, 10, 15)
        mock_db_client.get_volume.assert_any_call(user_id, today, today)
        
        # Check monthly volume call (only if daily check passed or was not the reason for failure)
        if expected_result or (daily_vol + amount <= TIER_LIMITS.get(tier, {}).get("daily_limit", 0)):
            start_of_month = today.replace(day=1)
            mock_db_client.get_volume.assert_any_call(user_id, start_of_month, today)
        
    @pytest.mark.asyncio
    async def test_check_kyc_requirements_user_fetch_failure(self, kyc_checker_instance, mock_db_client, user_id):
        """Test that a failure to fetch user data raises a KYCServiceError."""
        mock_db_client.fetch_user.side_effect = Exception("DB Connection Error")
        
        with pytest.raises(KYCServiceError, match="Failed to fetch user data: DB Connection Error"):
            await kyc_checker_instance.check_kyc_requirements(user_id, 100)

    @pytest.mark.asyncio
    async def test_check_kyc_requirements_volume_fetch_failure(self, kyc_checker_instance, mock_db_client, user_id):
        """Test that a failure to fetch transaction volume raises a KYCServiceError (implicitly)."""
        # The current implementation of check_kyc_requirements handles volume fetch failure 
        # by letting the exception propagate from _get_transaction_history.
        # Since _get_transaction_history is an internal method, we'll mock it directly 
        # to test the exception handling if it were to be more complex.
        # For the current simple propagation, we'll ensure the mock is called.
        
        mock_db_client.fetch_user.return_value = {"kyc_tier": 1}
        mock_db_client.get_volume.side_effect = Exception("Volume Fetch Error")
        
        # The exception will propagate from the internal method.
        with pytest.raises(Exception, match="Volume Fetch Error"):
            await kyc_checker_instance.check_kyc_requirements(user_id, 100)
            
    @pytest.mark.asyncio
    async def test_check_kyc_requirements_invalid_tier_in_user_data(self, kyc_checker_instance, mock_db_client, user_id):
        """Test handling of an invalid tier level returned in user data."""
        mock_db_client.fetch_user.return_value = {"kyc_tier": 99}
        
        # The error should be raised from get_tier_limits inside check_kyc_requirements
        with pytest.raises(KYCServiceError, match="Invalid KYC tier level: 99"):
            await kyc_checker_instance.check_kyc_requirements(user_id, 100)

    # --- Test calculate_daily_limit_remaining method ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tier, daily_vol, expected_remaining", [
        (1, 100, 900.0), # Limit 1000, Used 100, Remaining 900
        (2, 9000, 1000.0), # Limit 10000, Used 9000, Remaining 1000
        (3, 100000, 0.0), # Limit 100000, Used 100000, Remaining 0
        (1, 1001, 0.0), # Over limit, should return 0.0
        (0, 0, 0.0), # Tier 0 limit is 0
    ])
    async def test_calculate_daily_limit_remaining_success(self, kyc_checker_instance, mock_db_client, user_id, tier, daily_vol, expected_remaining):
        """Test calculation of remaining daily limit."""
        mock_db_client.fetch_user.return_value = {"kyc_tier": tier}
        mock_db_client.get_volume.return_value = daily_vol
        
        remaining = await kyc_checker_instance.calculate_daily_limit_remaining(user_id)
        assert remaining == expected_remaining
        
        today = date(2025, 10, 15)
        mock_db_client.get_volume.assert_called_once_with(user_id, today, today)

    @pytest.mark.asyncio
    async def test_calculate_daily_limit_remaining_user_fetch_failure(self, kyc_checker_instance, mock_db_client, user_id):
        """Test daily limit calculation failure when fetching user data fails."""
        mock_db_client.fetch_user.side_effect = Exception("DB Error")
        
        with pytest.raises(KYCServiceError, match="Failed to fetch user data: DB Error"):
            await kyc_checker_instance.calculate_daily_limit_remaining(user_id)

    # --- Test calculate_monthly_limit_remaining method ---

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tier, monthly_vol, expected_remaining", [
        (1, 500, 4500.0), # Limit 5000, Used 500, Remaining 4500
        (2, 49000, 1000.0), # Limit 50000, Used 49000, Remaining 1000
        (3, 500000, 0.0), # Limit 500000, Used 500000, Remaining 0
        (2, 50001, 0.0), # Over limit, should return 0.0
        (0, 0, 0.0), # Tier 0 limit is 0
    ])
    async def test_calculate_monthly_limit_remaining_success(self, kyc_checker_instance, mock_db_client, user_id, tier, monthly_vol, expected_remaining):
        """Test calculation of remaining monthly limit."""
        mock_db_client.fetch_user.return_value = {"kyc_tier": tier}
        mock_db_client.get_volume.return_value = monthly_vol
        
        remaining = await kyc_checker_instance.calculate_monthly_limit_remaining(user_id)
        assert remaining == expected_remaining
        
        today = date(2025, 10, 15)
        start_of_month = today.replace(day=1)
        mock_db_client.get_volume.assert_called_once_with(user_id, start_of_month, today)

    @pytest.mark.asyncio
    async def test_calculate_monthly_limit_remaining_user_fetch_failure(self, kyc_checker_instance, mock_db_client, user_id):
        """Test monthly limit calculation failure when fetching user data fails."""
        mock_db_client.fetch_user.side_effect = Exception("DB Error")
        
        with pytest.raises(KYCServiceError, match="Failed to fetch user data: DB Error"):
            await kyc_checker_instance.calculate_monthly_limit_remaining(user_id)

    # --- Test internal methods (for coverage) ---
    # Although internal, we can test them via the instance if needed, 
    # but for 90%+ coverage, testing the public methods that call them is usually sufficient.
    # The public methods already cover the success and failure paths of the internal methods.
    
    # Test for the internal _get_user_data and _get_transaction_history are implicitly covered 
    # by the tests for check_kyc_requirements, calculate_daily_limit_remaining, and 
    # calculate_monthly_limit_remaining.
    
    # To ensure 100% coverage on the internal methods' call signatures, we can add a simple 
    # test for the `perform_external_kyc_check` function if it were part of the class, 
    # but since it's a standalone example function, we'll skip it and focus on the class.
    
    # The current test suite covers:
    # - KYCChecker.__init__ (via fixture)
    # - get_tier_limits (success, invalid tier)
    # - calculate_required_tier (all tiers, edge cases)
    # - check_kyc_requirements (success, daily fail, monthly fail, max_tx fail, user fetch fail, volume fetch fail, invalid tier)
    # - calculate_daily_limit_remaining (success, user fetch fail)
    # - calculate_monthly_limit_remaining (success, user fetch fail)
    # - _get_user_data (implicitly via public methods)
    # - _get_transaction_history (implicitly via public methods)
    # - KYCServiceError (implicitly via raises)
    # - TIER_LIMITS (implicitly via tests)
    
    pass
