"""
Real-time Monitor Service
Nigerian Remittance Platform
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from models.transaction import Transaction, TransactionStatus, TransactionType
from models.alert import Alert, AlertSeverity
from schemas.dashboard import (
    DashboardMetrics, CurrencyBreakdown, HourlyVolume, TopCorridor,
    DashboardFilters
)
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class RealtimeMonitorService:
    """Service for real-time monitoring operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_metrics(self) -> DashboardMetrics:
        """Calculate and return dashboard metrics"""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_hour = now - timedelta(hours=1)

        # Active transactions (pending or processing)
        active_transactions = self.db.query(func.count(Transaction.id)).filter(
            Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.PROCESSING])
        ).scalar() or 0

        # Total volume (last 24 hours)
        total_volume = self.db.query(func.sum(Transaction.amount)).filter(
            and_(
                Transaction.created_at >= last_24h,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0.0

        # Success rate (last 24 hours)
        total_transactions = self.db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= last_24h
        ).scalar() or 0
        
        successful_transactions = self.db.query(func.count(Transaction.id)).filter(
            and_(
                Transaction.created_at >= last_24h,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).scalar() or 0
        
        success_rate = (successful_transactions / total_transactions * 100) if total_transactions > 0 else 0.0

        # Average processing time (last 24 hours)
        avg_processing_time = self.db.query(func.avg(Transaction.processing_time)).filter(
            and_(
                Transaction.created_at >= last_24h,
                Transaction.processing_time.isnot(None)
            )
        ).scalar() or 0.0

        # Failed transactions (last 24 hours)
        failed_transactions = self.db.query(func.count(Transaction.id)).filter(
            and_(
                Transaction.created_at >= last_24h,
                Transaction.status == TransactionStatus.FAILED
            )
        ).scalar() or 0

        # Pending transactions
        pending_transactions = self.db.query(func.count(Transaction.id)).filter(
            Transaction.status == TransactionStatus.PENDING
        ).scalar() or 0

        # Transactions per minute (last hour)
        transactions_last_hour = self.db.query(func.count(Transaction.id)).filter(
            Transaction.created_at >= last_hour
        ).scalar() or 0
        transactions_per_minute = transactions_last_hour / 60.0

        # Active users (last hour)
        active_users = self.db.query(func.count(func.distinct(Transaction.sender_id))).filter(
            Transaction.created_at >= last_hour
        ).scalar() or 0

        # Total fees collected (last 24 hours)
        total_fees = self.db.query(func.sum(Transaction.fee_amount)).filter(
            and_(
                Transaction.created_at >= last_24h,
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.fee_amount.isnot(None)
            )
        ).scalar() or 0.0

        # Currency breakdown (last 24 hours)
        currency_breakdown = self._get_currency_breakdown(last_24h)

        # Hourly volume (last 24 hours)
        hourly_volume = self._get_hourly_volume(last_24h)

        # Top corridors (last 24 hours)
        top_corridors = self._get_top_corridors(last_24h)

        return DashboardMetrics(
            active_transactions=active_transactions,
            total_volume=total_volume,
            success_rate=round(success_rate, 2),
            average_processing_time=round(avg_processing_time, 2),
            failed_transactions=failed_transactions,
            pending_transactions=pending_transactions,
            transactions_per_minute=round(transactions_per_minute, 2),
            active_users=active_users,
            total_fees_collected=total_fees,
            currency_breakdown=currency_breakdown,
            hourly_volume=hourly_volume,
            top_corridors=top_corridors
        )

    def _get_currency_breakdown(self, since: datetime) -> List[CurrencyBreakdown]:
        """Get currency breakdown"""
        results = self.db.query(
            Transaction.currency,
            func.sum(Transaction.amount).label('volume'),
            func.count(Transaction.id).label('count')
        ).filter(
            and_(
                Transaction.created_at >= since,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).group_by(Transaction.currency).all()

        total_volume = sum(r.volume for r in results)
        
        return [
            CurrencyBreakdown(
                currency=r.currency,
                volume=float(r.volume),
                count=r.count,
                percentage=round((r.volume / total_volume * 100) if total_volume > 0 else 0, 2)
            )
            for r in results
        ]

    def _get_hourly_volume(self, since: datetime) -> List[HourlyVolume]:
        """Get hourly volume"""
        # Group by hour
        results = self.db.query(
            func.date_trunc('hour', Transaction.created_at).label('hour'),
            func.sum(Transaction.amount).label('volume'),
            func.count(Transaction.id).label('count')
        ).filter(
            and_(
                Transaction.created_at >= since,
                Transaction.status == TransactionStatus.COMPLETED
            )
        ).group_by(func.date_trunc('hour', Transaction.created_at)).order_by('hour').all()

        return [
            HourlyVolume(
                hour=r.hour.isoformat() if r.hour else '',
                volume=float(r.volume),
                count=r.count
            )
            for r in results
        ]

    def _get_top_corridors(self, since: datetime, limit: int = 5) -> List[TopCorridor]:
        """Get top payment corridors"""
        # This is a simplified version - in production, you'd join with user country data
        # For now, returning mock data structure
        return [
            TopCorridor(
                from_country="Nigeria",
                to_country="United States",
                volume=150000.0,
                count=450
            ),
            TopCorridor(
                from_country="Nigeria",
                to_country="United Kingdom",
                volume=120000.0,
                count=380
            ),
            TopCorridor(
                from_country="Nigeria",
                to_country="Canada",
                volume=80000.0,
                count=250
            )
        ]

    def get_transactions(
        self,
        filters: Optional[DashboardFilters] = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "-created_at"
    ) -> Tuple[List[Transaction], int]:
        """Get transactions with filters and pagination"""
        query = self.db.query(Transaction)

        # Apply filters
        if filters:
            if filters.status:
                query = query.filter(Transaction.status.in_(filters.status))
            
            if filters.type:
                query = query.filter(Transaction.type.in_(filters.type))
            
            if filters.date_from:
                query = query.filter(Transaction.created_at >= filters.date_from)
            
            if filters.date_to:
                query = query.filter(Transaction.created_at <= filters.date_to)
            
            if filters.currency:
                query = query.filter(Transaction.currency.in_(filters.currency))
            
            if filters.min_amount is not None:
                query = query.filter(Transaction.amount >= filters.min_amount)
            
            if filters.max_amount is not None:
                query = query.filter(Transaction.amount <= filters.max_amount)

        # Get total count
        total = query.count()

        # Apply sorting
        if sort.startswith('-'):
            # Descending
            sort_field = sort[1:]
            query = query.order_by(desc(getattr(Transaction, sort_field)))
        else:
            # Ascending
            query = query.order_by(getattr(Transaction, sort))

        # Apply pagination
        offset = (page - 1) * page_size
        transactions = query.offset(offset).limit(page_size).all()

        return transactions, total

    def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID"""
        return self.db.query(Transaction).filter(Transaction.id == transaction_id).first()

    def get_active_transactions(self, page: int = 1, page_size: int = 20) -> Tuple[List[Transaction], int]:
        """Get active (pending or processing) transactions"""
        query = self.db.query(Transaction).filter(
            Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.PROCESSING])
        ).order_by(desc(Transaction.created_at))

        total = query.count()
        offset = (page - 1) * page_size
        transactions = query.offset(offset).limit(page_size).all()

        return transactions, total

    def get_alerts(
        self,
        acknowledged: bool = False,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Alert], int]:
        """Get alerts"""
        query = self.db.query(Alert).filter(Alert.acknowledged == acknowledged).order_by(desc(Alert.timestamp))

        total = query.count()
        offset = (page - 1) * page_size
        alerts = query.offset(offset).limit(page_size).all()

        return alerts, total

    def acknowledge_alert(self, alert_id: str, user_id: str) -> Optional[Alert]:
        """Acknowledge an alert"""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = user_id
            self.db.commit()
            self.db.refresh(alert)
        
        return alert

    def export_transactions_csv(self, filters: Optional[DashboardFilters] = None) -> str:
        """Export transactions to CSV"""
        import csv
        import io

        transactions, _ = self.get_transactions(filters=filters, page=1, page_size=10000)

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'ID', 'Reference', 'Amount', 'Currency', 'Status', 'Type',
            'Sender', 'Recipient', 'Payment Method', 'Created At'
        ])

        # Write data
        for txn in transactions:
            writer.writerow([
                txn.id,
                txn.reference,
                txn.amount,
                txn.currency,
                txn.status.value,
                txn.type.value,
                txn.sender.email if txn.sender else '',
                txn.recipient.email if txn.recipient else '',
                txn.payment_method,
                txn.created_at.isoformat() if txn.created_at else ''
            ])

        return output.getvalue()
