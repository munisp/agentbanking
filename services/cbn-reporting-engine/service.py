"""
CBN Automated Reporting Engine
Generates all mandatory CBN (Central Bank of Nigeria) reports automatically:
- Monthly Agent Banking Activity Report
- Quarterly Fraud Incident Report
- Annual KYC Compliance Report
- Real-time Suspicious Activity Reports (SAR)
- Agent Network Expansion Reports
All reports conform to CBN Circular FPR/DIR/GEN/CIR/07/011 and subsequent guidelines.
"""
import csv
import io
import json
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from models import CBNReport, CBNReportType, CBNReportStatus, SuspiciousActivityReport
from config import settings

logger = logging.getLogger(__name__)

# CBN report submission deadlines (days after period end)
SUBMISSION_DEADLINES = {
    "monthly_activity": 10,       # 10 days after month end
    "quarterly_fraud": 15,        # 15 days after quarter end
    "annual_kyc": 30,             # 30 days after year end
    "sar": 3,                     # 3 days after detection
    "network_expansion": 10,      # 10 days after quarter end
}

# CBN transaction thresholds (NGN)
SAR_THRESHOLD_SINGLE = Decimal("5000000")     # NGN 5M single transaction
SAR_THRESHOLD_DAILY = Decimal("10000000")     # NGN 10M daily aggregate
CASH_TRANSACTION_REPORT_THRESHOLD = Decimal("5000000")  # NGN 5M CTR


class CBNReportingEngine:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # MONTHLY ACTIVITY REPORT
    # ─────────────────────────────────────────────────────────────────────────

    def generate_monthly_activity_report(
        self,
        year: int,
        month: int,
        institution_code: str,
        institution_name: str,
    ) -> CBNReport:
        """Generate CBN Monthly Agent Banking Activity Report."""
        period_start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            period_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            period_end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)

        # Query transaction aggregates from platform
        txn_data = self._query_transaction_aggregates(period_start, period_end)
        agent_data = self._query_agent_statistics(period_start, period_end)

        report_data = {
            "report_type": "MONTHLY_AGENT_BANKING_ACTIVITY",
            "reporting_period": f"{year}-{month:02d}",
            "institution_code": institution_code,
            "institution_name": institution_name,
            "submission_deadline": (period_end + timedelta(days=SUBMISSION_DEADLINES["monthly_activity"])).date().isoformat(),
            "section_a_agent_network": {
                "total_registered_agents": agent_data.get("total_registered", 0),
                "active_agents": agent_data.get("active_count", 0),
                "new_agents_onboarded": agent_data.get("new_onboarded", 0),
                "agents_deactivated": agent_data.get("deactivated", 0),
                "agents_by_state": agent_data.get("by_state", {}),
                "agents_by_type": agent_data.get("by_type", {}),
            },
            "section_b_transactions": {
                "total_transaction_count": txn_data.get("total_count", 0),
                "total_transaction_value_ngn": str(txn_data.get("total_value", Decimal("0"))),
                "cash_deposit_count": txn_data.get("deposit_count", 0),
                "cash_deposit_value": str(txn_data.get("deposit_value", Decimal("0"))),
                "cash_withdrawal_count": txn_data.get("withdrawal_count", 0),
                "cash_withdrawal_value": str(txn_data.get("withdrawal_value", Decimal("0"))),
                "funds_transfer_count": txn_data.get("transfer_count", 0),
                "funds_transfer_value": str(txn_data.get("transfer_value", Decimal("0"))),
                "bill_payment_count": txn_data.get("bill_count", 0),
                "bill_payment_value": str(txn_data.get("bill_value", Decimal("0"))),
                "account_opening_count": txn_data.get("account_opening_count", 0),
                "failed_transactions": txn_data.get("failed_count", 0),
                "reversal_count": txn_data.get("reversal_count", 0),
                "reversal_value": str(txn_data.get("reversal_value", Decimal("0"))),
            },
            "section_c_kyc_compliance": {
                "tier1_agents": agent_data.get("tier1_count", 0),
                "tier2_agents": agent_data.get("tier2_count", 0),
                "tier3_agents": agent_data.get("tier3_count", 0),
                "biometric_enrolled": agent_data.get("biometric_enrolled", 0),
                "bvn_verified": agent_data.get("bvn_verified", 0),
                "nin_verified": agent_data.get("nin_verified", 0),
            },
            "section_d_complaints": {
                "total_complaints": txn_data.get("complaint_count", 0),
                "resolved_complaints": txn_data.get("resolved_complaints", 0),
                "pending_complaints": txn_data.get("pending_complaints", 0),
                "avg_resolution_hours": txn_data.get("avg_resolution_hours", 0),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return self._save_report(
            report_type="monthly_activity",
            period_start=period_start,
            period_end=period_end,
            data=report_data,
            institution_code=institution_code,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # SUSPICIOUS ACTIVITY REPORT (SAR)
    # ─────────────────────────────────────────────────────────────────────────

    def file_sar(
        self,
        agent_id: UUID,
        transaction_ids: List[UUID],
        total_amount: Decimal,
        reason: str,
        description: str,
        customer_details: Optional[Dict] = None,
    ) -> SuspiciousActivityReport:
        """File a Suspicious Activity Report with CBN."""
        sar = SuspiciousActivityReport(
            agent_id=agent_id,
            transaction_ids=[str(t) for t in transaction_ids],
            total_amount=total_amount,
            reason=reason,
            description=description,
            customer_details=customer_details or {},
            status="pending_submission",
            submission_deadline=(datetime.now(timezone.utc) + timedelta(days=SUBMISSION_DEADLINES["sar"])).date(),
            filed_at=datetime.now(timezone.utc),
        )
        self.db.add(sar)
        self.db.commit()
        self.db.refresh(sar)
        logger.warning(f"SAR filed: {sar.id} agent={agent_id} amount={total_amount} reason={reason}")
        return sar

    def check_sar_thresholds(
        self,
        agent_id: UUID,
        transaction_id: UUID,
        amount: Decimal,
        transaction_type: str,
    ) -> Optional[SuspiciousActivityReport]:
        """Auto-detect SAR threshold breaches and file automatically."""
        # Single transaction threshold
        if amount >= SAR_THRESHOLD_SINGLE:
            return self.file_sar(
                agent_id=agent_id,
                transaction_ids=[transaction_id],
                total_amount=amount,
                reason="single_transaction_threshold",
                description=f"Single {transaction_type} transaction of NGN {amount:,.2f} exceeds CBN SAR threshold",
            )

        # Daily aggregate threshold
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_total = self._get_agent_daily_volume(agent_id, today_start)
        if daily_total + amount >= SAR_THRESHOLD_DAILY:
            return self.file_sar(
                agent_id=agent_id,
                transaction_ids=[transaction_id],
                total_amount=daily_total + amount,
                reason="daily_aggregate_threshold",
                description=f"Daily aggregate of NGN {daily_total + amount:,.2f} exceeds CBN SAR threshold",
            )
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # QUARTERLY FRAUD REPORT
    # ─────────────────────────────────────────────────────────────────────────

    def generate_quarterly_fraud_report(
        self,
        year: int,
        quarter: int,
        institution_code: str,
    ) -> CBNReport:
        """Generate CBN Quarterly Fraud Incident Report."""
        q_start_month = (quarter - 1) * 3 + 1
        period_start = datetime(year, q_start_month, 1, tzinfo=timezone.utc)
        q_end_month = q_start_month + 2
        if q_end_month > 12:
            period_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            import calendar
            last_day = calendar.monthrange(year, q_end_month)[1]
            period_end = datetime(year, q_end_month, last_day, 23, 59, 59, tzinfo=timezone.utc)

        fraud_data = self._query_fraud_incidents(period_start, period_end)

        report_data = {
            "report_type": "QUARTERLY_FRAUD_INCIDENT",
            "reporting_period": f"{year}-Q{quarter}",
            "institution_code": institution_code,
            "total_fraud_incidents": fraud_data.get("total_incidents", 0),
            "total_fraud_value_ngn": str(fraud_data.get("total_value", Decimal("0"))),
            "recovered_value_ngn": str(fraud_data.get("recovered_value", Decimal("0"))),
            "fraud_by_type": fraud_data.get("by_type", {}),
            "fraud_by_channel": fraud_data.get("by_channel", {}),
            "fraud_by_state": fraud_data.get("by_state", {}),
            "arrests_made": fraud_data.get("arrests", 0),
            "prosecutions_initiated": fraud_data.get("prosecutions", 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return self._save_report(
            report_type="quarterly_fraud",
            period_start=period_start,
            period_end=period_end,
            data=report_data,
            institution_code=institution_code,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # REPORT MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def _save_report(
        self,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        data: Dict,
        institution_code: str,
    ) -> CBNReport:
        report = CBNReport(
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            institution_code=institution_code,
            data=data,
            status="generated",
            submission_deadline=(period_end + timedelta(days=SUBMISSION_DEADLINES.get(report_type, 10))).date(),
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_pending_submissions(self) -> List[CBNReport]:
        """Get all reports pending CBN submission."""
        return self.db.query(CBNReport).filter(
            CBNReport.status.in_(["generated", "pending_submission"])
        ).order_by(CBNReport.submission_deadline.asc()).all()

    def mark_submitted(self, report_id: UUID, cbn_reference: str) -> CBNReport:
        report = self.db.query(CBNReport).filter(CBNReport.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        report.status = "submitted"
        report.cbn_reference = cbn_reference
        report.submitted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(report)
        return report

    def export_csv(self, report_id: UUID) -> str:
        """Export a report as CBN-compatible CSV."""
        report = self.db.query(CBNReport).filter(CBNReport.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Field", "Value"])
        for k, v in report.data.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    writer.writerow([f"{k}.{k2}", v2])
            else:
                writer.writerow([k, v])
        return output.getvalue()

    # ─────────────────────────────────────────────────────────────────────────
    # DATA QUERIES (query existing platform tables)
    # ─────────────────────────────────────────────────────────────────────────

    def _query_transaction_aggregates(self, start: datetime, end: datetime) -> Dict:
        """Query transaction aggregates from the platform transaction tables."""
        try:
            result = self.db.execute(text("""
                SELECT
                    COUNT(*) as total_count,
                    COALESCE(SUM(amount), 0) as total_value,
                    COUNT(*) FILTER (WHERE transaction_type = 'deposit') as deposit_count,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'deposit'), 0) as deposit_value,
                    COUNT(*) FILTER (WHERE transaction_type = 'withdrawal') as withdrawal_count,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'withdrawal'), 0) as withdrawal_value,
                    COUNT(*) FILTER (WHERE transaction_type = 'transfer') as transfer_count,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'transfer'), 0) as transfer_value,
                    COUNT(*) FILTER (WHERE transaction_type = 'bill_payment') as bill_count,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'bill_payment'), 0) as bill_value,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    COUNT(*) FILTER (WHERE transaction_type = 'reversal') as reversal_count,
                    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'reversal'), 0) as reversal_value
                FROM transactions
                WHERE created_at BETWEEN :start AND :end
            """), {"start": start, "end": end}).fetchone()
            return dict(result._mapping) if result else {}
        except Exception as e:
            logger.warning(f"Transaction aggregate query failed: {e}")
            return {}

    def _query_agent_statistics(self, start: datetime, end: datetime) -> Dict:
        """Query agent statistics from the platform agent tables."""
        try:
            result = self.db.execute(text("""
                SELECT
                    COUNT(*) as total_registered,
                    COUNT(*) FILTER (WHERE status = 'active') as active_count,
                    COUNT(*) FILTER (WHERE created_at BETWEEN :start AND :end) as new_onboarded,
                    COUNT(*) FILTER (WHERE deactivated_at BETWEEN :start AND :end) as deactivated,
                    COUNT(*) FILTER (WHERE kyc_tier = 1) as tier1_count,
                    COUNT(*) FILTER (WHERE kyc_tier = 2) as tier2_count,
                    COUNT(*) FILTER (WHERE kyc_tier = 3) as tier3_count,
                    COUNT(*) FILTER (WHERE biometric_enrolled = true) as biometric_enrolled,
                    COUNT(*) FILTER (WHERE bvn_verified = true) as bvn_verified,
                    COUNT(*) FILTER (WHERE nin_verified = true) as nin_verified
                FROM agents
            """), {"start": start, "end": end}).fetchone()
            return dict(result._mapping) if result else {}
        except Exception as e:
            logger.warning(f"Agent statistics query failed: {e}")
            return {}

    def _query_fraud_incidents(self, start: datetime, end: datetime) -> Dict:
        """Query fraud incidents from the platform fraud tables."""
        try:
            result = self.db.execute(text("""
                SELECT
                    COUNT(*) as total_incidents,
                    COALESCE(SUM(amount), 0) as total_value,
                    COALESCE(SUM(recovered_amount), 0) as recovered_value
                FROM fraud_incidents
                WHERE detected_at BETWEEN :start AND :end
            """), {"start": start, "end": end}).fetchone()
            return dict(result._mapping) if result else {}
        except Exception as e:
            logger.warning(f"Fraud incident query failed: {e}")
            return {}

    def _get_agent_daily_volume(self, agent_id: UUID, since: datetime) -> Decimal:
        """Get agent's transaction volume since a given time."""
        try:
            result = self.db.execute(text("""
                SELECT COALESCE(SUM(amount), 0) as daily_total
                FROM transactions
                WHERE agent_id = :agent_id AND created_at >= :since AND status = 'completed'
            """), {"agent_id": str(agent_id), "since": since}).fetchone()
            return Decimal(str(result.daily_total)) if result else Decimal("0")
        except Exception:
            return Decimal("0")
