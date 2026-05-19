"""
Nigeria VAT Management & Reporting Service
Implements the Finance Act 2020 (effective February 2020) and Finance Act 2021:
- VAT Rate: 7.5% (increased from 5% by Finance Act 2020)
- Exempt goods/services per FIRS guidelines
- Zero-rated goods/services
- VAT registration threshold: NGN 25,000,000 annual turnover
- Monthly VAT returns (Form 002) due by 21st of following month
- Withholding VAT (WVAT) for government contracts
- Input VAT credit mechanism
- VAT on digital/electronic services (Finance Act 2021)
- Reverse charge mechanism for imported services
"""

import os
import csv
import json
import io
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime, Date,
    Enum as SAEnum, Text, ForeignKey, Index, func
)
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()

# ─────────────────────────────────────────────
# CONSTANTS — Nigeria VAT (Finance Act 2020/2021)
# ─────────────────────────────────────────────
VAT_STANDARD_RATE = Decimal("0.075")          # 7.5%
VAT_REGISTRATION_THRESHOLD = Decimal("25000000")  # NGN 25M annual turnover
WVAT_RATE = Decimal("0.075")                  # Withholding VAT = full VAT rate
PENALTY_RATE_PER_MONTH = Decimal("0.05")      # 5% per month late filing penalty
INTEREST_RATE_PER_ANNUM = Decimal("21.5")     # CBN MPR + 5% for late payment


class VATCategory(str, Enum):
    STANDARD_RATED = "STANDARD_RATED"          # 7.5%
    ZERO_RATED = "ZERO_RATED"                  # 0% (exports, basic food, etc.)
    EXEMPT = "EXEMPT"                          # No VAT (financial services, medical, education)
    DIGITAL_SERVICE = "DIGITAL_SERVICE"        # 7.5% — Finance Act 2021
    IMPORTED_SERVICE = "IMPORTED_SERVICE"      # Reverse charge 7.5%


class TransactionType(str, Enum):
    SALE = "SALE"
    PURCHASE = "PURCHASE"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    DIGITAL_SERVICE = "DIGITAL_SERVICE"
    GOVERNMENT_CONTRACT = "GOVERNMENT_CONTRACT"


class ReturnStatus(str, Enum):
    DRAFT = "DRAFT"
    FILED = "FILED"
    ASSESSED = "ASSESSED"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    AMENDED = "AMENDED"


# ─────────────────────────────────────────────
# EXEMPT GOODS & SERVICES (FIRS Schedule)
# ─────────────────────────────────────────────
EXEMPT_CATEGORIES = {
    "financial_services": [
        "banking_fees", "insurance_premiums", "loan_interest",
        "money_transfer_fees", "foreign_exchange", "agency_banking_fees",
    ],
    "medical": [
        "medical_services", "pharmaceutical_products", "medical_equipment",
        "hospital_services", "ambulance_services",
    ],
    "education": [
        "tuition_fees", "educational_materials", "school_fees",
        "examination_fees", "educational_books",
    ],
    "basic_food": [
        "unprocessed_food", "agricultural_produce", "livestock",
        "poultry", "fish_unprocessed",
    ],
    "exports": [
        "goods_exported", "services_exported",
    ],
}

ZERO_RATED_GOODS = [
    "non_oil_exports", "goods_purchased_by_diplomats",
    "goods_purchased_by_international_organizations",
]


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────

class VATRegistration(Base):
    __tablename__ = "vat_registrations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id = Column(String(100), nullable=False, unique=True)  # merchant/agent ID
    entity_name = Column(String(200), nullable=False)
    entity_type = Column(String(50), nullable=False)  # MERCHANT, AGENT, CORPORATE
    tin = Column(String(20), nullable=True)            # Tax Identification Number
    vat_registration_number = Column(String(30), nullable=True)
    registration_date = Column(Date, nullable=True)
    annual_turnover_ngn = Column(Numeric(20, 2), default=Decimal("0"))
    is_registered = Column(Boolean, default=False)
    is_exempt = Column(Boolean, default=False)
    exemption_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VATTransaction(Base):
    __tablename__ = "vat_transactions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id = Column(String(100), nullable=False, index=True)
    transaction_ref = Column(String(100), nullable=False, unique=True)
    transaction_date = Column(DateTime, nullable=False)
    transaction_type = Column(SAEnum(TransactionType), nullable=False)
    vat_category = Column(SAEnum(VATCategory), nullable=False)
    description = Column(String(500), nullable=False)
    taxable_amount = Column(Numeric(20, 2), nullable=False)
    vat_rate = Column(Numeric(6, 4), nullable=False)
    vat_amount = Column(Numeric(20, 2), nullable=False)
    total_amount = Column(Numeric(20, 2), nullable=False)
    is_input_vat = Column(Boolean, default=False)   # True = purchase (claimable)
    is_output_vat = Column(Boolean, default=False)  # True = sale (payable)
    is_withholding_vat = Column(Boolean, default=False)
    customer_tin = Column(String(20), nullable=True)
    supplier_tin = Column(String(20), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    period = Column(String(7), nullable=False, index=True)  # YYYY-MM
    return_id = Column(String(36), ForeignKey("vat_returns.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class VATReturn(Base):
    __tablename__ = "vat_returns"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id = Column(String(100), nullable=False, index=True)
    entity_name = Column(String(200), nullable=False)
    tin = Column(String(20), nullable=True)
    vat_registration_number = Column(String(30), nullable=True)
    period = Column(String(7), nullable=False)  # YYYY-MM
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    filing_deadline = Column(Date, nullable=False)
    status = Column(SAEnum(ReturnStatus), default=ReturnStatus.DRAFT)
    # Output VAT (Sales)
    total_taxable_sales = Column(Numeric(20, 2), default=Decimal("0"))
    total_exempt_sales = Column(Numeric(20, 2), default=Decimal("0"))
    total_zero_rated_sales = Column(Numeric(20, 2), default=Decimal("0"))
    output_vat = Column(Numeric(20, 2), default=Decimal("0"))
    # Input VAT (Purchases)
    total_taxable_purchases = Column(Numeric(20, 2), default=Decimal("0"))
    input_vat_claimable = Column(Numeric(20, 2), default=Decimal("0"))
    # Net VAT
    net_vat_payable = Column(Numeric(20, 2), default=Decimal("0"))
    vat_credit_carried_forward = Column(Numeric(20, 2), default=Decimal("0"))
    # Withholding VAT
    wvat_deducted = Column(Numeric(20, 2), default=Decimal("0"))
    # Penalties
    late_filing_penalty = Column(Numeric(20, 2), default=Decimal("0"))
    late_payment_interest = Column(Numeric(20, 2), default=Decimal("0"))
    # Payment
    amount_paid = Column(Numeric(20, 2), default=Decimal("0"))
    payment_date = Column(Date, nullable=True)
    firs_receipt_number = Column(String(100), nullable=True)
    filed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_vat_return_entity_period", "entity_id", "period"),
    )


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────

class VATTransactionCreate(BaseModel):
    entity_id: str
    transaction_ref: str
    transaction_date: datetime
    transaction_type: TransactionType
    vat_category: VATCategory
    description: str
    taxable_amount: Decimal
    is_input_vat: bool = False
    is_output_vat: bool = False
    is_withholding_vat: bool = False
    customer_tin: Optional[str] = None
    supplier_tin: Optional[str] = None
    invoice_number: Optional[str] = None


class VATReturnRequest(BaseModel):
    entity_id: str
    entity_name: str
    year: int
    month: int = Field(..., ge=1, le=12)
    tin: Optional[str] = None
    vat_registration_number: Optional[str] = None
    previous_credit: Decimal = Decimal("0")


class VATReturnResponse(BaseModel):
    id: str
    entity_id: str
    entity_name: str
    period: str
    status: ReturnStatus
    total_taxable_sales: Decimal
    output_vat: Decimal
    input_vat_claimable: Decimal
    net_vat_payable: Decimal
    vat_credit_carried_forward: Decimal
    late_filing_penalty: Decimal
    filing_deadline: date
    firs_receipt_number: Optional[str]

    class Config:
        from_attributes = True


class VATRegistrationRequest(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    tin: Optional[str] = None
    annual_turnover_ngn: Decimal = Decimal("0")


class VATSummaryResponse(BaseModel):
    entity_id: str
    period: str
    output_vat: Decimal
    input_vat: Decimal
    net_payable: Decimal
    effective_rate: Decimal
    transactions_count: int


# ─────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────

class NigeriaVATService:
    """
    Nigeria VAT Management Service implementing Finance Act 2020/2021.
    Handles VAT calculation, input credit, returns filing, and FIRS reporting.
    """

    def __init__(self, db: Session):
        self.db = db

    def _round_vat(self, amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_vat(self, taxable_amount: Decimal, category: VATCategory) -> Tuple[Decimal, Decimal]:
        """
        Returns (vat_amount, total_amount) for a given taxable amount and category.
        """
        if category in (VATCategory.EXEMPT,):
            return Decimal("0"), taxable_amount
        if category == VATCategory.ZERO_RATED:
            return Decimal("0"), taxable_amount
        # Standard, Digital, Imported — all 7.5%
        vat = self._round_vat(taxable_amount * VAT_STANDARD_RATE)
        return vat, taxable_amount + vat

    def is_vat_exempt(self, service_code: str) -> bool:
        """Check if a service/product code is VAT-exempt per FIRS schedule."""
        for category, codes in EXEMPT_CATEGORIES.items():
            if service_code in codes:
                return True
        return False

    def check_registration_required(self, entity_id: str) -> Dict:
        """
        Check if an entity is required to register for VAT based on turnover threshold.
        Threshold: NGN 25,000,000 annual turnover (Finance Act 2020).
        """
        reg = self.db.query(VATRegistration).filter(VATRegistration.entity_id == entity_id).first()
        if not reg:
            return {"required": False, "reason": "Entity not found", "threshold_ngn": str(VAT_REGISTRATION_THRESHOLD)}

        required = reg.annual_turnover_ngn >= VAT_REGISTRATION_THRESHOLD
        return {
            "entity_id": entity_id,
            "entity_name": reg.entity_name,
            "annual_turnover_ngn": str(reg.annual_turnover_ngn),
            "threshold_ngn": str(VAT_REGISTRATION_THRESHOLD),
            "registration_required": required,
            "currently_registered": reg.is_registered,
            "is_exempt": reg.is_exempt,
            "exemption_reason": reg.exemption_reason,
            "action_required": required and not reg.is_registered and not reg.is_exempt,
        }

    def register_for_vat(self, req: VATRegistrationRequest) -> VATRegistration:
        """Register an entity for VAT with FIRS."""
        existing = self.db.query(VATRegistration).filter(VATRegistration.entity_id == req.entity_id).first()
        if existing:
            existing.entity_name = req.entity_name
            existing.tin = req.tin
            existing.annual_turnover_ngn = req.annual_turnover_ngn
            if req.annual_turnover_ngn >= VAT_REGISTRATION_THRESHOLD:
                existing.is_registered = True
                existing.registration_date = date.today()
            self.db.commit()
            self.db.refresh(existing)
            return existing

        reg = VATRegistration(
            entity_id=req.entity_id,
            entity_name=req.entity_name,
            entity_type=req.entity_type,
            tin=req.tin,
            annual_turnover_ngn=req.annual_turnover_ngn,
            is_registered=req.annual_turnover_ngn >= VAT_REGISTRATION_THRESHOLD,
            registration_date=date.today() if req.annual_turnover_ngn >= VAT_REGISTRATION_THRESHOLD else None,
        )
        self.db.add(reg)
        self.db.commit()
        self.db.refresh(reg)
        return reg

    def record_vat_transaction(self, req: VATTransactionCreate) -> VATTransaction:
        """Record a VAT transaction (sale or purchase)."""
        vat_amount, total = self.calculate_vat(req.taxable_amount, req.vat_category)
        period = req.transaction_date.strftime("%Y-%m")

        txn = VATTransaction(
            entity_id=req.entity_id,
            transaction_ref=req.transaction_ref,
            transaction_date=req.transaction_date,
            transaction_type=req.transaction_type,
            vat_category=req.vat_category,
            description=req.description,
            taxable_amount=req.taxable_amount,
            vat_rate=VAT_STANDARD_RATE if req.vat_category not in (VATCategory.EXEMPT, VATCategory.ZERO_RATED) else Decimal("0"),
            vat_amount=vat_amount,
            total_amount=total,
            is_input_vat=req.is_input_vat,
            is_output_vat=req.is_output_vat,
            is_withholding_vat=req.is_withholding_vat,
            customer_tin=req.customer_tin,
            supplier_tin=req.supplier_tin,
            invoice_number=req.invoice_number,
            period=period,
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def generate_monthly_return(self, req: VATReturnRequest) -> VATReturn:
        """
        Generate VAT Form 002 (Monthly Return) for FIRS submission.
        Due by 21st of the following month.
        """
        period = f"{req.year}-{req.month:02d}"
        period_start = date(req.year, req.month, 1)
        last_day = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        # Filing deadline: 21st of following month
        if req.month == 12:
            filing_deadline = date(req.year + 1, 1, 21)
        else:
            filing_deadline = date(req.year, req.month + 1, 21)

        # Aggregate transactions for the period
        txns = (
            self.db.query(VATTransaction)
            .filter(
                VATTransaction.entity_id == req.entity_id,
                VATTransaction.period == period,
            )
            .all()
        )

        # Output VAT (sales)
        output_txns = [t for t in txns if t.is_output_vat]
        total_taxable_sales = sum(t.taxable_amount for t in output_txns)
        total_exempt_sales = sum(
            t.taxable_amount for t in output_txns if t.vat_category == VATCategory.EXEMPT
        )
        total_zero_rated_sales = sum(
            t.taxable_amount for t in output_txns if t.vat_category == VATCategory.ZERO_RATED
        )
        output_vat = sum(t.vat_amount for t in output_txns)

        # Input VAT (purchases — claimable credit)
        input_txns = [t for t in txns if t.is_input_vat]
        total_taxable_purchases = sum(t.taxable_amount for t in input_txns)
        input_vat_claimable = sum(t.vat_amount for t in input_txns)

        # Withholding VAT deducted by customers
        wvat = sum(t.vat_amount for t in txns if t.is_withholding_vat)

        # Net VAT payable
        net_vat = output_vat - input_vat_claimable - wvat - req.previous_credit
        net_vat_payable = max(net_vat, Decimal("0"))
        credit_carried_forward = abs(min(net_vat, Decimal("0")))

        # Late filing penalty
        today = date.today()
        late_penalty = Decimal("0")
        if today > filing_deadline:
            months_late = ((today.year - filing_deadline.year) * 12 +
                           today.month - filing_deadline.month)
            late_penalty = self._round_vat(net_vat_payable * PENALTY_RATE_PER_MONTH * months_late)

        vat_return = VATReturn(
            entity_id=req.entity_id,
            entity_name=req.entity_name,
            tin=req.tin,
            vat_registration_number=req.vat_registration_number,
            period=period,
            period_start=period_start,
            period_end=last_day,
            filing_deadline=filing_deadline,
            status=ReturnStatus.DRAFT,
            total_taxable_sales=total_taxable_sales,
            total_exempt_sales=total_exempt_sales,
            total_zero_rated_sales=total_zero_rated_sales,
            output_vat=output_vat,
            total_taxable_purchases=total_taxable_purchases,
            input_vat_claimable=input_vat_claimable,
            net_vat_payable=net_vat_payable,
            vat_credit_carried_forward=credit_carried_forward,
            wvat_deducted=wvat,
            late_filing_penalty=late_penalty,
        )
        self.db.add(vat_return)
        self.db.commit()
        self.db.refresh(vat_return)

        # Link transactions to this return
        for t in txns:
            t.return_id = vat_return.id
        self.db.commit()

        logger.info(f"Generated VAT return for {req.entity_id} period {period}: net payable NGN {net_vat_payable}")
        return vat_return

    def file_return(self, return_id: str, firs_receipt_number: str) -> VATReturn:
        """Mark a VAT return as filed with FIRS."""
        vat_return = self.db.query(VATReturn).filter(VATReturn.id == return_id).first()
        if not vat_return:
            raise ValueError(f"VAT return {return_id} not found")
        vat_return.status = ReturnStatus.FILED
        vat_return.firs_receipt_number = firs_receipt_number
        vat_return.filed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(vat_return)
        return vat_return

    def record_payment(self, return_id: str, amount_paid: Decimal, payment_date: date) -> VATReturn:
        """Record VAT payment against a filed return."""
        vat_return = self.db.query(VATReturn).filter(VATReturn.id == return_id).first()
        if not vat_return:
            raise ValueError(f"VAT return {return_id} not found")
        vat_return.amount_paid = amount_paid
        vat_return.payment_date = payment_date
        if amount_paid >= vat_return.net_vat_payable:
            vat_return.status = ReturnStatus.PAID
        self.db.commit()
        self.db.refresh(vat_return)
        return vat_return

    def get_vat_summary(self, entity_id: str, period: str) -> VATSummaryResponse:
        """Get VAT summary for an entity for a given period."""
        txns = (
            self.db.query(VATTransaction)
            .filter(VATTransaction.entity_id == entity_id, VATTransaction.period == period)
            .all()
        )
        output_vat = sum(t.vat_amount for t in txns if t.is_output_vat)
        input_vat = sum(t.vat_amount for t in txns if t.is_input_vat)
        net = output_vat - input_vat
        total_sales = sum(t.taxable_amount for t in txns if t.is_output_vat)
        effective_rate = (output_vat / total_sales * 100) if total_sales > 0 else Decimal("0")
        return VATSummaryResponse(
            entity_id=entity_id,
            period=period,
            output_vat=output_vat,
            input_vat=input_vat,
            net_payable=max(net, Decimal("0")),
            effective_rate=self._round_vat(effective_rate),
            transactions_count=len(txns),
        )

    def export_vat_schedule(self, entity_id: str, period: str) -> str:
        """Export VAT schedule as CSV for FIRS submission."""
        txns = (
            self.db.query(VATTransaction)
            .filter(VATTransaction.entity_id == entity_id, VATTransaction.period == period)
            .order_by(VATTransaction.transaction_date)
            .all()
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Transaction Ref", "Date", "Type", "VAT Category", "Description",
            "Taxable Amount (NGN)", "VAT Rate (%)", "VAT Amount (NGN)",
            "Total Amount (NGN)", "Input/Output", "Invoice Number",
            "Customer TIN", "Supplier TIN"
        ])
        for t in txns:
            writer.writerow([
                t.transaction_ref,
                t.transaction_date.strftime("%Y-%m-%d"),
                t.transaction_type.value,
                t.vat_category.value,
                t.description,
                str(t.taxable_amount),
                str(float(t.vat_rate) * 100),
                str(t.vat_amount),
                str(t.total_amount),
                "INPUT" if t.is_input_vat else "OUTPUT",
                t.invoice_number or "",
                t.customer_tin or "",
                t.supplier_tin or "",
            ])
        return output.getvalue()

    def get_annual_vat_report(self, entity_id: str, year: int) -> Dict:
        """Generate annual VAT report for FIRS annual returns."""
        annual_data = {
            "entity_id": entity_id,
            "year": year,
            "months": [],
            "annual_totals": {
                "total_taxable_sales": Decimal("0"),
                "total_output_vat": Decimal("0"),
                "total_input_vat": Decimal("0"),
                "total_net_vat_paid": Decimal("0"),
                "total_penalties": Decimal("0"),
            },
        }
        for month in range(1, 13):
            period = f"{year}-{month:02d}"
            vat_return = (
                self.db.query(VATReturn)
                .filter(VATReturn.entity_id == entity_id, VATReturn.period == period)
                .first()
            )
            if vat_return:
                month_data = {
                    "period": period,
                    "status": vat_return.status.value,
                    "output_vat": str(vat_return.output_vat),
                    "input_vat": str(vat_return.input_vat_claimable),
                    "net_payable": str(vat_return.net_vat_payable),
                    "amount_paid": str(vat_return.amount_paid),
                    "penalty": str(vat_return.late_filing_penalty),
                    "filed_at": str(vat_return.filed_at) if vat_return.filed_at else None,
                }
                annual_data["months"].append(month_data)
                annual_data["annual_totals"]["total_taxable_sales"] += vat_return.total_taxable_sales
                annual_data["annual_totals"]["total_output_vat"] += vat_return.output_vat
                annual_data["annual_totals"]["total_input_vat"] += vat_return.input_vat_claimable
                annual_data["annual_totals"]["total_net_vat_paid"] += vat_return.amount_paid
                annual_data["annual_totals"]["total_penalties"] += vat_return.late_filing_penalty

        # Convert Decimals to strings for JSON serialization
        for k, v in annual_data["annual_totals"].items():
            annual_data["annual_totals"][k] = str(v)

        return annual_data
