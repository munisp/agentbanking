"""API Router for CBN Reporting Engine."""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from models import (MonthlyReportRequest, QuarterlyFraudReportRequest,
                     SARRequest, ReportResponse, SARResponse)
from service import CBNReportingEngine
from config import get_db

router = APIRouter(prefix="/api/v1/cbn-reports", tags=["CBN Reporting Engine"])


def get_svc(db: Session = Depends(get_db)) -> CBNReportingEngine:
    return CBNReportingEngine(db)


@router.post("/monthly-activity", response_model=ReportResponse)
def generate_monthly(payload: MonthlyReportRequest, svc: CBNReportingEngine = Depends(get_svc)):
    return svc.generate_monthly_activity_report(
        year=payload.year, month=payload.month,
        institution_code=payload.institution_code,
        institution_name=payload.institution_name,
    )


@router.post("/quarterly-fraud", response_model=ReportResponse)
def generate_quarterly_fraud(payload: QuarterlyFraudReportRequest, svc: CBNReportingEngine = Depends(get_svc)):
    return svc.generate_quarterly_fraud_report(
        year=payload.year, quarter=payload.quarter,
        institution_code=payload.institution_code,
    )


@router.post("/sar", response_model=SARResponse, summary="File a Suspicious Activity Report")
def file_sar(payload: SARRequest, svc: CBNReportingEngine = Depends(get_svc)):
    return svc.file_sar(
        agent_id=payload.agent_id,
        transaction_ids=payload.transaction_ids,
        total_amount=payload.total_amount,
        reason=payload.reason,
        description=payload.description,
        customer_details=payload.customer_details,
    )


@router.get("/pending", response_model=List[ReportResponse])
def get_pending(svc: CBNReportingEngine = Depends(get_svc)):
    return svc.get_pending_submissions()


@router.post("/{report_id}/submit", response_model=ReportResponse)
def mark_submitted(report_id: UUID, cbn_reference: str, svc: CBNReportingEngine = Depends(get_svc)):
    try:
        return svc.mark_submitted(report_id, cbn_reference)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{report_id}/export/csv", response_class=PlainTextResponse)
def export_csv(report_id: UUID, svc: CBNReportingEngine = Depends(get_svc)):
    try:
        return svc.export_csv(report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/health")
def health():
    return {"status": "healthy", "service": "cbn-reporting-engine"}
