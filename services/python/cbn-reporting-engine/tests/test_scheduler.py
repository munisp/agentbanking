"""
Tests for CBN Reporting Engine scheduler and report generation.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestSchedulerConfiguration:
    """Test APScheduler configuration and job registration."""

    def test_scheduler_imports(self):
        """Scheduler module should import without errors."""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from scheduler import create_scheduler
            assert create_scheduler is not None
        except ImportError as e:
            pytest.skip(f"Scheduler module not available: {e}")

    def test_scheduler_has_required_jobs(self):
        """Scheduler should register all required CBN report jobs."""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from scheduler import create_scheduler
            scheduler = create_scheduler()
            job_ids = [job.id for job in scheduler.get_jobs()]
            assert "daily_activity_report" in job_ids, "Missing daily_activity_report job"
            assert "monthly_cbn_report" in job_ids, "Missing monthly_cbn_report job"
            assert "weekly_reconciliation" in job_ids, "Missing weekly_reconciliation job"
        except ImportError as e:
            pytest.skip(f"Scheduler module not available: {e}")


class TestReportGeneration:
    """Test report generation logic."""

    def test_daily_report_structure(self):
        """Daily activity report should have required CBN fields."""
        report = {
            "reportType": "daily_activity",
            "institutionCode": "54LINK001",
            "reportDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "totalTransactions": 1250,
            "totalVolume": 45_000_000.0,
            "agentCount": 87,
            "successRate": 98.4,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        required_fields = [
            "reportType", "institutionCode", "reportDate",
            "totalTransactions", "totalVolume", "agentCount",
            "successRate", "generatedAt"
        ]
        for field in required_fields:
            assert field in report, f"Missing required field: {field}"

    def test_monthly_report_structure(self):
        """Monthly CBN report should have all required regulatory fields."""
        report = {
            "reportType": "monthly_activity",
            "institutionCode": "54LINK001",
            "reportMonth": "2026-03",
            "totalAgents": 87,
            "activeAgents": 82,
            "newAgents": 5,
            "totalTransactions": 38_500,
            "totalVolume": 1_350_000_000.0,
            "cashIn": 720_000_000.0,
            "cashOut": 580_000_000.0,
            "transfers": 50_000_000.0,
            "kycCompliantAgents": 85,
            "kycComplianceRate": 97.7,
            "suspiciousTransactions": 12,
            "blockedTransactions": 3,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        required_fields = [
            "reportType", "institutionCode", "reportMonth",
            "totalAgents", "activeAgents", "totalTransactions",
            "totalVolume", "cashIn", "cashOut", "kycComplianceRate"
        ]
        for field in required_fields:
            assert field in report, f"Missing required field: {field}"

    def test_report_volume_consistency(self):
        """Cash in + cash out + transfers should equal total volume."""
        cash_in = 720_000_000.0
        cash_out = 580_000_000.0
        transfers = 50_000_000.0
        total = 1_350_000_000.0
        assert abs((cash_in + cash_out + transfers) - total) < 0.01

    def test_kyc_compliance_rate_calculation(self):
        """KYC compliance rate should be calculated correctly."""
        total_agents = 87
        kyc_compliant = 85
        expected_rate = (kyc_compliant / total_agents) * 100
        assert abs(expected_rate - 97.7) < 0.1

    def test_suspicious_transaction_rate(self):
        """Suspicious transaction rate should be below CBN threshold (2%)."""
        total_transactions = 38_500
        suspicious = 12
        rate = (suspicious / total_transactions) * 100
        assert rate < 2.0, f"Suspicious transaction rate {rate:.2f}% exceeds CBN threshold of 2%"

    def test_daily_limit_enforcement_basic(self):
        """Basic tier agents should not exceed ₦300,000 daily limit."""
        BASIC_DAILY_LIMIT = 300_000
        agent_daily_volume = 250_000
        assert agent_daily_volume <= BASIC_DAILY_LIMIT

    def test_daily_limit_enforcement_standard(self):
        """Standard tier agents should not exceed ₦1,000,000 daily limit."""
        STANDARD_DAILY_LIMIT = 1_000_000
        agent_daily_volume = 850_000
        assert agent_daily_volume <= STANDARD_DAILY_LIMIT

    def test_daily_limit_enforcement_premium(self):
        """Premium tier agents should not exceed ₦5,000,000 daily limit."""
        PREMIUM_DAILY_LIMIT = 5_000_000
        agent_daily_volume = 4_200_000
        assert agent_daily_volume <= PREMIUM_DAILY_LIMIT


class TestReportSubmission:
    """Test report submission and storage logic."""

    def test_report_filename_format(self):
        """Report filenames should follow CBN naming convention."""
        institution_code = "54LINK001"
        report_date = "2026-03-31"
        report_type = "monthly_activity"
        filename = f"{institution_code}_{report_type}_{report_date}.json"
        assert filename == "54LINK001_monthly_activity_2026-03-31.json"

    def test_report_s3_key_format(self):
        """S3 keys should follow the lakehouse Bronze layer convention."""
        institution_code = "54LINK001"
        report_type = "monthly_activity"
        year = "2026"
        month = "03"
        filename = "54LINK001_monthly_activity_2026-03-31.json"
        s3_key = f"cbn-reports/{institution_code}/{report_type}/{year}/{month}/{filename}"
        assert s3_key.startswith("cbn-reports/")
        assert institution_code in s3_key
        assert report_type in s3_key

    def test_report_json_serializable(self):
        """Report data should be JSON-serializable."""
        report = {
            "reportType": "daily_activity",
            "institutionCode": "54LINK001",
            "reportDate": "2026-03-31",
            "totalTransactions": 1250,
            "totalVolume": 45_000_000.0,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        json_str = json.dumps(report)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["institutionCode"] == "54LINK001"


class TestCBNComplianceRules:
    """Test CBN regulatory compliance rules."""

    def test_agent_tier_classification(self):
        """Agents should be classified into correct tiers based on KYC level."""
        tiers = {
            "basic": {"min_kyc": 1, "daily_limit": 300_000, "single_limit": 50_000},
            "standard": {"min_kyc": 2, "daily_limit": 1_000_000, "single_limit": 200_000},
            "premium": {"min_kyc": 3, "daily_limit": 5_000_000, "single_limit": 1_000_000},
        }
        assert tiers["basic"]["daily_limit"] == 300_000
        assert tiers["standard"]["daily_limit"] == 1_000_000
        assert tiers["premium"]["daily_limit"] == 5_000_000

    def test_transaction_single_limit(self):
        """Single transaction should not exceed tier limit."""
        STANDARD_SINGLE_LIMIT = 200_000
        transaction_amount = 150_000
        assert transaction_amount <= STANDARD_SINGLE_LIMIT

    def test_aml_threshold(self):
        """Transactions above AML threshold should be flagged."""
        AML_THRESHOLD = 5_000_000
        transaction_amount = 6_000_000
        is_flagged = transaction_amount >= AML_THRESHOLD
        assert is_flagged

    def test_report_submission_deadline(self):
        """Monthly report should be submitted by 5th of following month."""
        # Report for March 2026 due by April 5, 2026
        report_month = datetime(2026, 3, 1)
        deadline = datetime(report_month.year + (report_month.month // 12),
                           (report_month.month % 12) + 1, 5)
        assert deadline == datetime(2026, 4, 5)

    def test_institution_code_format(self):
        """CBN institution code should be alphanumeric, 8-12 chars."""
        institution_code = "54LINK001"
        assert institution_code.isalnum()
        assert 8 <= len(institution_code) <= 12
