"""ERPNext Agent Business Accounting & Performance Reports — API Router"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from service import (
    ERPNextIntegrationService,
    SyncTransactionRequest,
    FinancialSummaryRequest,
    AgentPerformanceReport,
)
from config import get_db

router = APIRouter(prefix="/erp", tags=["ERPNext Integration"])


def get_svc(db: Session = Depends(get_db)) -> ERPNextIntegrationService:
    return ERPNextIntegrationService(db)


# ─── Agent Setup ─────────────────────────────


@router.post("/agents/{agent_id}/setup")
def setup_agent_accounting(
    agent_id: str,
    agent_name: str = Query(...),
    phone: str = Query(...),
    email: Optional[str] = Query(None),
    vat_number: Optional[str] = Query(None),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Set up ERPNext accounting profile for an agent/vendor."""
    profile = svc.setup_agent_accounting(agent_id, agent_name, phone, email, vat_number)
    return {
        "agent_id": profile.agent_id,
        "erp_customer_name": profile.erp_customer_name,
        "erp_company": profile.erp_company,
        "vat_registered": profile.vat_registered,
        "auto_sync_enabled": profile.auto_sync_enabled,
        "created_at": str(profile.created_at),
    }


# ─── Transaction Sync ─────────────────────────


@router.post("/sync/transaction")
def sync_transaction(
    payload: SyncTransactionRequest, svc: ERPNextIntegrationService = Depends(get_svc)
):
    """Sync a 54agent transaction to ERPNext (creates Sales Invoice + Journal Entry)."""
    log = svc.sync_transaction(payload)
    return {
        "sync_id": log.id,
        "status": log.status,
        "erp_document_id": log.erp_document_id,
        "error_message": log.error_message,
        "synced_at": str(log.synced_at) if log.synced_at else None,
    }


@router.get("/sync/{agent_id}/status")
def get_sync_status(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get recent ERPNext sync status for an agent."""
    return svc.get_sync_status(agent_id, limit)


@router.post("/sync/{agent_id}/retry-failed")
def retry_failed_syncs(
    agent_id: str, svc: ERPNextIntegrationService = Depends(get_svc)
):
    """Retry all failed sync operations for an agent."""
    return svc.retry_failed_syncs(agent_id)


# ─── Financial Reports ────────────────────────


@router.get("/reports/{agent_id}/performance", response_model=AgentPerformanceReport)
def get_performance_report(
    agent_id: str,
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get comprehensive agent performance report with transaction analytics and financial KPIs."""
    return svc.get_agent_performance_report(agent_id, from_date, to_date)


@router.post("/reports/financial-summary")
def get_financial_summary(
    payload: FinancialSummaryRequest, svc: ERPNextIntegrationService = Depends(get_svc)
):
    """Get complete financial summary: P&L, Balance Sheet, and performance metrics."""
    return svc.get_financial_summary(payload)


@router.get("/reports/{agent_id}/profit-loss")
def get_profit_loss(
    agent_id: str,
    from_date: str = Query(...),
    to_date: str = Query(...),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get Profit & Loss statement from ERPNext."""
    from service import AgentAccountingProfile

    profile = (
        svc.db.query(AgentAccountingProfile)
        .filter(AgentAccountingProfile.agent_id == agent_id)
        .first()
    )
    company = profile.erp_company if profile else svc.erp.company
    return svc.erp.get_profit_loss(company, from_date, to_date)


@router.get("/reports/{agent_id}/balance-sheet")
def get_balance_sheet(
    agent_id: str,
    as_of_date: str = Query(...),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get Balance Sheet from ERPNext."""
    from service import AgentAccountingProfile

    profile = (
        svc.db.query(AgentAccountingProfile)
        .filter(AgentAccountingProfile.agent_id == agent_id)
        .first()
    )
    company = profile.erp_company if profile else svc.erp.company
    return svc.erp.get_balance_sheet(company, as_of_date)


@router.get("/reports/{agent_id}/cash-flow")
def get_cash_flow(
    agent_id: str,
    from_date: str = Query(...),
    to_date: str = Query(...),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get Cash Flow statement from ERPNext."""
    from service import AgentAccountingProfile

    profile = (
        svc.db.query(AgentAccountingProfile)
        .filter(AgentAccountingProfile.agent_id == agent_id)
        .first()
    )
    company = profile.erp_company if profile else svc.erp.company
    return svc.erp.get_cash_flow(company, from_date, to_date)


@router.get("/reports/{agent_id}/trial-balance")
def get_trial_balance(
    agent_id: str,
    from_date: str = Query(...),
    to_date: str = Query(...),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get Trial Balance from ERPNext."""
    from service import AgentAccountingProfile

    profile = (
        svc.db.query(AgentAccountingProfile)
        .filter(AgentAccountingProfile.agent_id == agent_id)
        .first()
    )
    company = profile.erp_company if profile else svc.erp.company
    return svc.erp.get_trial_balance(company, from_date, to_date)


@router.get("/reports/{agent_id}/customer-ledger")
def get_customer_ledger(
    agent_id: str,
    from_date: str = Query(...),
    to_date: str = Query(...),
    svc: ERPNextIntegrationService = Depends(get_svc),
):
    """Get customer ledger (outstanding invoices, payments) from ERPNext."""
    from service import AgentAccountingProfile

    profile = (
        svc.db.query(AgentAccountingProfile)
        .filter(AgentAccountingProfile.agent_id == agent_id)
        .first()
    )
    if not profile or not profile.erp_customer_name:
        raise HTTPException(
            status_code=404,
            detail="Agent accounting not set up. Call /erp/agents/{agent_id}/setup first.",
        )
    return svc.erp.get_customer_ledger(profile.erp_customer_name, from_date, to_date)


@router.get("/health")
def health():
    return {"status": "ok", "service": "erpnext-integration"}
