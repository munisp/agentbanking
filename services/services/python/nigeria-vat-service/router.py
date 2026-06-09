"""Nigeria VAT Management & Reporting — API Router"""
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from .service import (
    NigeriaVATService, VATTransactionCreate, VATReturnRequest,
    VATRegistrationRequest, VATReturnResponse, VATSummaryResponse, VATCategory
)
from .config import get_db

router = APIRouter(prefix="/vat", tags=["Nigeria VAT"])


def get_svc(db: Session = Depends(get_db)) -> NigeriaVATService:
    return NigeriaVATService(db)


@router.post("/register")
def register_for_vat(payload: VATRegistrationRequest, svc: NigeriaVATService = Depends(get_svc)):
    """Register an entity for VAT with FIRS. Threshold: NGN 25M annual turnover."""
    reg = svc.register_for_vat(payload)
    return {
        "entity_id": reg.entity_id,
        "entity_name": reg.entity_name,
        "is_registered": reg.is_registered,
        "registration_date": str(reg.registration_date) if reg.registration_date else None,
        "vat_registration_number": reg.vat_registration_number,
    }


@router.get("/registration-check/{entity_id}")
def check_registration(entity_id: str, svc: NigeriaVATService = Depends(get_svc)):
    """Check if an entity is required to register for VAT."""
    return svc.check_registration_required(entity_id)


@router.post("/transactions", summary="Record a VAT transaction")
def record_transaction(payload: VATTransactionCreate, svc: NigeriaVATService = Depends(get_svc)):
    """Record a VAT transaction (sale or purchase) with automatic VAT calculation."""
    txn = svc.record_vat_transaction(payload)
    return {
        "id": txn.id,
        "transaction_ref": txn.transaction_ref,
        "taxable_amount": str(txn.taxable_amount),
        "vat_rate_pct": str(float(txn.vat_rate) * 100),
        "vat_amount": str(txn.vat_amount),
        "total_amount": str(txn.total_amount),
        "period": txn.period,
    }


@router.post("/calculate")
def calculate_vat(taxable_amount: Decimal = Query(...), category: VATCategory = Query(VATCategory.STANDARD_RATED), svc: NigeriaVATService = Depends(get_svc)):
    """Calculate VAT for a given amount and category."""
    vat, total = svc.calculate_vat(taxable_amount, category)
    return {
        "taxable_amount": str(taxable_amount),
        "category": category.value,
        "vat_rate_pct": "7.5" if category not in (VATCategory.EXEMPT, VATCategory.ZERO_RATED) else "0",
        "vat_amount": str(vat),
        "total_amount": str(total),
        "regulatory_basis": "Finance Act 2020 — Section 4",
    }


@router.post("/returns/generate", response_model=VATReturnResponse)
def generate_monthly_return(payload: VATReturnRequest, svc: NigeriaVATService = Depends(get_svc)):
    """Generate monthly VAT return (Form 002) for FIRS submission."""
    return svc.generate_monthly_return(payload)


@router.post("/returns/{return_id}/file")
def file_return(return_id: str, firs_receipt_number: str = Query(...), svc: NigeriaVATService = Depends(get_svc)):
    """Mark a VAT return as filed with FIRS."""
    try:
        r = svc.file_return(return_id, firs_receipt_number)
        return {"return_id": r.id, "status": r.status.value, "firs_receipt": r.firs_receipt_number}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/returns/{return_id}/payment")
def record_payment(return_id: str, amount_paid: Decimal = Query(...), payment_date: str = Query(...), svc: NigeriaVATService = Depends(get_svc)):
    """Record VAT payment against a filed return."""
    from datetime import date
    try:
        r = svc.record_payment(return_id, amount_paid, date.fromisoformat(payment_date))
        return {"return_id": r.id, "status": r.status.value, "amount_paid": str(r.amount_paid)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/summary/{entity_id}/{period}", response_model=VATSummaryResponse)
def get_vat_summary(entity_id: str, period: str, svc: NigeriaVATService = Depends(get_svc)):
    """Get VAT summary for an entity for a given period (YYYY-MM)."""
    return svc.get_vat_summary(entity_id, period)


@router.get("/schedule/{entity_id}/{period}/csv", response_class=PlainTextResponse)
def export_vat_schedule(entity_id: str, period: str, svc: NigeriaVATService = Depends(get_svc)):
    """Export VAT schedule as CSV for FIRS submission."""
    return svc.export_vat_schedule(entity_id, period)


@router.get("/annual-report/{entity_id}/{year}")
def get_annual_report(entity_id: str, year: int, svc: NigeriaVATService = Depends(get_svc)):
    """Get annual VAT report for FIRS annual returns."""
    return svc.get_annual_vat_report(entity_id, year)


@router.get("/exempt-categories")
def get_exempt_categories():
    """List all VAT-exempt goods and services per FIRS schedule."""
    from .service import EXEMPT_CATEGORIES, ZERO_RATED_GOODS
    return {
        "exempt_categories": EXEMPT_CATEGORIES,
        "zero_rated_goods": ZERO_RATED_GOODS,
        "standard_rate_pct": 7.5,
        "regulatory_basis": "Finance Act 2020 (effective February 2020)",
        "firs_reference": "FIRS Information Circular No. 2020/01",
    }


@router.get("/health")
def health():
    return {"status": "ok", "service": "nigeria-vat-service"}
