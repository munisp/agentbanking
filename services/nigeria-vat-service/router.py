"""Nigeria VAT Management & Reporting — API Router"""

from decimal import Decimal
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from service import (
    AutomationConfigSchema,
    NigeriaVATService,
    RecordPaymentRequest,
    VATReturn,
    VATTransactionCreate,
    VATReturnRequest,
    VATRegistrationRequest,
    VATReturnResponse,
    VATSummaryResponse,
    VATCategory,
)
from config import get_db

router = APIRouter(prefix="/vat", tags=["Nigeria VAT"])


def get_svc(db: Session = Depends(get_db)) -> NigeriaVATService:
    return NigeriaVATService(db)


# ── Registration ──────────────────────────────────────────────────────────────

@router.post("/register")
def register_for_vat(
    payload: VATRegistrationRequest, svc: NigeriaVATService = Depends(get_svc)
):
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


# ── Transactions ──────────────────────────────────────────────────────────────

@router.post("/transactions", summary="Record a VAT transaction")
def record_transaction(
    payload: VATTransactionCreate, svc: NigeriaVATService = Depends(get_svc)
):
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


@router.get("/transactions")
def list_transactions(
    svc: NigeriaVATService = Depends(get_svc),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List VAT transactions across all businesses."""
    return svc.list_transactions(limit=limit, offset=offset)


# ── Calculate ─────────────────────────────────────────────────────────────────

@router.post("/calculate")
def calculate_vat(
    taxable_amount: Decimal = Query(...),
    category: VATCategory = Query(VATCategory.STANDARD_RATED),
    svc: NigeriaVATService = Depends(get_svc),
):
    """Calculate VAT for a given amount and category."""
    vat, total = svc.calculate_vat(taxable_amount, category)
    return {
        "taxable_amount": str(taxable_amount),
        "category": category.value,
        "vat_rate_pct": (
            "7.5"
            if category not in (VATCategory.EXEMPT, VATCategory.ZERO_RATED)
            else "0"
        ),
        "vat_amount": str(vat),
        "total_amount": str(total),
        "regulatory_basis": "Finance Act 2020 — Section 4",
    }


# ── Returns ───────────────────────────────────────────────────────────────────

@router.post("/returns/generate", response_model=VATReturnResponse)
def generate_monthly_return(
    payload: VATReturnRequest, svc: NigeriaVATService = Depends(get_svc)
):
    """
    Generate monthly VAT return (Form 002) for FIRS submission.
    Accepts either { entity_id, period: "YYYY-MM" } or
    { entity_id, year, month }. entity_name is optional — looked up
    from the entity's VAT registration automatically.
    """
    if not payload.period and (payload.year is None or payload.month is None):
        raise HTTPException(
            status_code=422,
            detail="Provide either 'period' (YYYY-MM) or both 'year' and 'month'",
        )
    return svc.generate_monthly_return(payload)


@router.post("/returns/{return_id}/file")
def file_return(
    return_id: str,
    svc: NigeriaVATService = Depends(get_svc),
    firs_receipt_number: str = Query(
        None,
        description="FIRS receipt number. If omitted, a system receipt is generated automatically.",
    ),
):
    """
    Mark a VAT return as filed with FIRS.
    If firs_receipt_number is not provided, the system auto-generates one
    (used by the automated filing flow).
    """
    try:
        if not firs_receipt_number:
            filed = svc.auto_file_return(return_id)
            if not filed:
                raise HTTPException(status_code=400, detail="Return not found or already filed")
            vat_return = svc.db.query(VATReturn).filter_by(id=return_id).first()
            return {
                "return_id": return_id,
                "status": vat_return.status.value if vat_return else "filed",
                "firs_receipt": vat_return.firs_receipt_number if vat_return else None,
            }
        r = svc.file_return(return_id, firs_receipt_number)
        return {
            "return_id": r.id,
            "status": r.status.value,
            "firs_receipt": r.firs_receipt_number,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/returns/{return_id}/payment")
def record_payment(
    return_id: str,
    body: RecordPaymentRequest = Body(...),
    svc: NigeriaVATService = Depends(get_svc),
):
    """Record VAT payment against a filed return."""
    from datetime import date as _date
    try:
        payment_date = _date.fromisoformat(body.payment_date)
        r = svc.record_payment(return_id, body.amount_paid, payment_date)
        return {
            "return_id": r.id,
            "status": r.status.value,
            "amount_paid": str(r.amount_paid),
            "payment_reference": body.payment_reference,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Summary & Reports ─────────────────────────────────────────────────────────

@router.get("/summary/{entity_id}/{period}", response_model=VATSummaryResponse)
def get_vat_summary(
    entity_id: str, period: str, svc: NigeriaVATService = Depends(get_svc)
):
    """Get VAT summary for an entity for a given period (YYYY-MM)."""
    return svc.get_vat_summary(entity_id, period)


@router.get("/businesses")
def list_vat_businesses(svc: NigeriaVATService = Depends(get_svc)):
    """List businesses/agents that have VAT transactions, with aggregate totals."""
    return svc.list_businesses_with_transactions()


@router.get("/schedule/{entity_id}/{period}/csv", response_class=PlainTextResponse)
def export_vat_schedule(
    entity_id: str, period: str, svc: NigeriaVATService = Depends(get_svc)
):
    """Export VAT schedule as CSV for FIRS submission."""
    return svc.export_vat_schedule(entity_id, period)


@router.get("/annual-report/{entity_id}/{year}")
def get_annual_report(
    entity_id: str, year: int, svc: NigeriaVATService = Depends(get_svc)
):
    """Get annual VAT report for FIRS annual returns."""
    return svc.get_annual_vat_report(entity_id, year)


@router.get("/exempt-categories")
def get_exempt_categories():
    """List all VAT-exempt goods and services per FIRS schedule."""
    from service import EXEMPT_CATEGORIES, ZERO_RATED_GOODS
    return {
        "exempt_categories": EXEMPT_CATEGORIES,
        "zero_rated_goods": ZERO_RATED_GOODS,
        "standard_rate_pct": 7.5,
        "regulatory_basis": "Finance Act 2020 (effective February 2020)",
        "firs_reference": "FIRS Information Circular No. 2020/01",
    }


# ── Automation Config ─────────────────────────────────────────────────────────

@router.get("/automation/{entity_id}")
def get_automation_config(
    entity_id: str, svc: NigeriaVATService = Depends(get_svc)
):
    """
    Get VAT automation preferences for an agent/business.
    Returns defaults (auto_record=true, auto_generate=true, auto_file=false)
    if no config exists yet.
    """
    cfg = svc.get_automation_config(entity_id)
    return {
        "entity_id": cfg.entity_id,
        "auto_record_vat": cfg.auto_record_vat,
        "auto_generate_return": cfg.auto_generate_return,
        "auto_file_firs": cfg.auto_file_firs,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.put("/automation/{entity_id}")
def update_automation_config(
    entity_id: str,
    body: AutomationConfigSchema,
    svc: NigeriaVATService = Depends(get_svc),
):
    """
    Update VAT automation preferences for an agent/business.

    - auto_record_vat: Record a VAT entry for every payment transaction (default: true)
    - auto_generate_return: Auto-generate monthly return on the 1st (default: true)
    - auto_file_firs: Auto-file the generated return with FIRS (default: false — agent must opt in)
    """
    cfg = svc.update_automation_config(entity_id, body)
    return {
        "entity_id": cfg.entity_id,
        "auto_record_vat": cfg.auto_record_vat,
        "auto_generate_return": cfg.auto_generate_return,
        "auto_file_firs": cfg.auto_file_firs,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "service": "nigeria-vat-service"}
