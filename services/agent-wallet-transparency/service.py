"""
Agent Wallet Transparency Service
Provides real-time, immutable wallet ledger views for agents.
Every debit, credit, commission, fee, and float movement is recorded
with full audit trail — addressing the #1 complaint about opaque balances.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from models import (
    WalletLedgerEntry, WalletStatement, WalletBalance,
    EntryType, LedgerEntryResponse, StatementResponse
)

logger = logging.getLogger(__name__)

# Fee schedule (transparent, published to agents)
FEE_SCHEDULE = {
    "cash_withdrawal": Decimal("0.005"),    # 0.5% of transaction
    "transfer": Decimal("0.003"),           # 0.3% of transaction
    "bill_payment": Decimal("50.00"),       # flat NGN 50
    "airtime": Decimal("0.015"),            # 1.5% of transaction
    "float_top_up": Decimal("0.00"),        # free
    "reversal": Decimal("0.00"),            # free
}

MAX_STATEMENT_DAYS = 365


class AgentWalletTransparencyService:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # BALANCE
    # ─────────────────────────────────────────────────────────────────────────

    def get_balance(self, agent_id: UUID) -> WalletBalance:
        """Get real-time wallet balance with full breakdown."""
        balance = self.db.query(WalletBalance).filter(
            WalletBalance.agent_id == agent_id
        ).first()
        if not balance:
            balance = WalletBalance(
                agent_id=agent_id,
                available_balance=Decimal("0.00"),
                ledger_balance=Decimal("0.00"),
                float_balance=Decimal("0.00"),
                commission_balance=Decimal("0.00"),
                pending_debit=Decimal("0.00"),
                pending_credit=Decimal("0.00"),
                currency="NGN",
            )
            self.db.add(balance)
            self.db.commit()
            self.db.refresh(balance)
        return balance

    def update_balance(
        self,
        agent_id: UUID,
        delta_available: Decimal = Decimal("0"),
        delta_float: Decimal = Decimal("0"),
        delta_commission: Decimal = Decimal("0"),
        delta_pending_debit: Decimal = Decimal("0"),
        delta_pending_credit: Decimal = Decimal("0"),
    ) -> WalletBalance:
        balance = self.get_balance(agent_id)
        balance.available_balance += delta_available
        balance.float_balance += delta_float
        balance.commission_balance += delta_commission
        balance.pending_debit += delta_pending_debit
        balance.pending_credit += delta_pending_credit
        balance.ledger_balance = (
            balance.available_balance + balance.float_balance + balance.commission_balance
        )
        balance.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(balance)
        return balance

    # ─────────────────────────────────────────────────────────────────────────
    # LEDGER ENTRIES
    # ─────────────────────────────────────────────────────────────────────────

    def record_entry(
        self,
        agent_id: UUID,
        entry_type: str,
        amount: Decimal,
        direction: str,           # "credit" or "debit"
        description: str,
        transaction_id: Optional[UUID] = None,
        reference: Optional[str] = None,
        fee_amount: Decimal = Decimal("0"),
        commission_amount: Decimal = Decimal("0"),
        customer_phone: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> WalletLedgerEntry:
        """Record an immutable ledger entry with running balance."""
        # Get current balance for running total
        balance = self.get_balance(agent_id)
        running_balance = balance.available_balance

        if direction == "credit":
            running_balance += amount
        elif direction == "debit":
            running_balance -= amount

        entry = WalletLedgerEntry(
            agent_id=agent_id,
            entry_type=entry_type,
            direction=direction,
            amount=amount,
            fee_amount=fee_amount,
            commission_amount=commission_amount,
            net_amount=amount - fee_amount if direction == "debit" else amount + commission_amount,
            running_balance=running_balance,
            description=description,
            transaction_id=transaction_id,
            reference=reference or f"TXN-{uuid4().hex[:12].upper()}",
            customer_phone=customer_phone,
            extra_metadata=metadata or {},
            value_date=datetime.now(timezone.utc),
        )
        self.db.add(entry)

        # Update balance atomically
        if direction == "credit":
            self.update_balance(agent_id, delta_available=amount + commission_amount)
        elif direction == "debit":
            self.update_balance(agent_id, delta_available=-(amount + fee_amount))

        self.db.commit()
        self.db.refresh(entry)
        logger.info(f"Ledger entry: agent={agent_id} type={entry_type} "
                    f"dir={direction} amount={amount} fee={fee_amount}")
        return entry

    def get_ledger_entries(
        self,
        agent_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entry_type: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict:
        """Get paginated ledger entries with filters."""
        query = self.db.query(WalletLedgerEntry).filter(
            WalletLedgerEntry.agent_id == agent_id
        )
        if start_date:
            query = query.filter(WalletLedgerEntry.value_date >= start_date)
        if end_date:
            query = query.filter(WalletLedgerEntry.value_date <= end_date)
        if entry_type:
            query = query.filter(WalletLedgerEntry.entry_type == entry_type)
        if direction:
            query = query.filter(WalletLedgerEntry.direction == direction)

        total = query.count()
        entries = query.order_by(desc(WalletLedgerEntry.value_date)).offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "entries": entries,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STATEMENTS
    # ─────────────────────────────────────────────────────────────────────────

    def generate_statement(
        self,
        agent_id: UUID,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> WalletStatement:
        """Generate a formal wallet statement for a date range."""
        if (end_date - start_date).days > MAX_STATEMENT_DAYS:
            raise ValueError(f"Statement period cannot exceed {MAX_STATEMENT_DAYS} days")

        entries_result = self.get_ledger_entries(
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )
        entries = entries_result["entries"]

        # Calculate summary
        total_credits = sum(e.amount for e in entries if e.direction == "credit")
        total_debits = sum(e.amount for e in entries if e.direction == "debit")
        total_fees = sum(e.fee_amount or Decimal("0") for e in entries)
        total_commissions = sum(e.commission_amount or Decimal("0") for e in entries)

        # Opening balance: balance just before start_date
        opening_entry = self.db.query(WalletLedgerEntry).filter(
            and_(
                WalletLedgerEntry.agent_id == agent_id,
                WalletLedgerEntry.value_date < start_date,
            )
        ).order_by(desc(WalletLedgerEntry.value_date)).first()
        opening_balance = opening_entry.running_balance if opening_entry else Decimal("0")
        closing_balance = opening_balance + total_credits - total_debits

        statement = WalletStatement(
            agent_id=agent_id,
            period_start=start_date,
            period_end=end_date,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            total_fees=total_fees,
            total_commissions=total_commissions,
            transaction_count=len(entries),
            format=format,
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(statement)
        self.db.commit()
        self.db.refresh(statement)
        return statement

    # ─────────────────────────────────────────────────────────────────────────
    # FEE TRANSPARENCY
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_fee(self, transaction_type: str, amount: Decimal) -> Decimal:
        """Calculate fee for a transaction type — transparent to agents."""
        rate = FEE_SCHEDULE.get(transaction_type, Decimal("0"))
        if rate < 1:  # percentage
            return (amount * rate).quantize(Decimal("0.01"))
        return rate  # flat fee

    def get_fee_schedule(self) -> Dict:
        """Return the published fee schedule for agent transparency."""
        return {
            k: {
                "type": "percentage" if v < 1 else "flat",
                "value": float(v),
                "display": f"{float(v)*100:.1f}%" if v < 1 else f"NGN {float(v):,.2f}",
            }
            for k, v in FEE_SCHEDULE.items()
        }

    # ─────────────────────────────────────────────────────────────────────────
    # ANALYTICS
    # ─────────────────────────────────────────────────────────────────────────

    def get_wallet_analytics(self, agent_id: UUID, days: int = 30) -> Dict:
        """Get wallet analytics for agent dashboard."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        entries = self.db.query(WalletLedgerEntry).filter(
            and_(
                WalletLedgerEntry.agent_id == agent_id,
                WalletLedgerEntry.value_date >= since,
            )
        ).all()

        # Daily breakdown
        daily = {}
        for e in entries:
            day = e.value_date.date().isoformat()
            if day not in daily:
                daily[day] = {"credits": 0, "debits": 0, "fees": 0, "commissions": 0}
            if e.direction == "credit":
                daily[day]["credits"] += float(e.amount)
                daily[day]["commissions"] += float(e.commission_amount or 0)
            else:
                daily[day]["debits"] += float(e.amount)
                daily[day]["fees"] += float(e.fee_amount or 0)

        # Type breakdown
        type_breakdown = {}
        for e in entries:
            t = e.entry_type
            if t not in type_breakdown:
                type_breakdown[t] = {"count": 0, "volume": 0}
            type_breakdown[t]["count"] += 1
            type_breakdown[t]["volume"] += float(e.amount)

        balance = self.get_balance(agent_id)
        return {
            "current_balance": float(balance.available_balance),
            "float_balance": float(balance.float_balance),
            "commission_balance": float(balance.commission_balance),
            "period_days": days,
            "total_credits": sum(float(e.amount) for e in entries if e.direction == "credit"),
            "total_debits": sum(float(e.amount) for e in entries if e.direction == "debit"),
            "total_fees_paid": sum(float(e.fee_amount or 0) for e in entries),
            "total_commissions_earned": sum(float(e.commission_amount or 0) for e in entries),
            "transaction_count": len(entries),
            "daily_breakdown": daily,
            "type_breakdown": type_breakdown,
        }
