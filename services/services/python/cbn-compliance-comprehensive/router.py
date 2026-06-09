"""CBN Comprehensive Compliance Reports — API Router"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from .service import (
    CBNComplianceService, MonthlyActivityRequest, QuarterlyFraudRequest,
    CTRRequest, SARRequest, AgentNetworkRequest, AMLReportRequest,
    KYCComplianceRequest, ReportResponse, ReportType
)
from .config import get_db

router = APIRouter(prefix="/cbn-compliance", tags=["CBN Compliance"])


def get_svc(db: Session = Depends(get_db)) -> CBNComplianceService:
    return CBNComplianceService(db)


@router.post("/reports/monthly-activity", response_model=ReportResponse)
def generate_monthly_activity(payload: MonthlyActivityRequest, svc: CBNComplianceService = Depends(get_svc)):
    """Generate CBN Monthly Activity Report (MAR) — due 10th of following month."""
    return svc.generate_monthly_activity_report(payload)


@router.post("/reports/quarterly-fraud", response_model=ReportResponse)
def generate_quarterly_fraud(payload: QuarterlyFraudRequest, svc: CBNComplianceService = Depends(get_svc)):
    """Generate CBN Quarterly Fraud & Forgeries Report (QFFR)."""
    return svc.generate_quarterly_fraud_report(payload)


@router.post("/reports/ctr", response_model=ReportResponse)
def generate_ctr(payload: CTRRequest, svc: CBNComplianceService = Depends(get_svc)):
    """Generate Currency Transaction Report (CTR) for transactions >= NGN 5,000,000."""
    return svc.generate_ctr_report(payload)


@router.post("/reports/agent-network", response_model=ReportResponse)
def generate_agent_network(payload: AgentNetworkRequest, svc: CBNComplianceService = Depends(get_svc)):
    """Generate Agent Network Activity Report — monthly CBN submission."""
    return svc.generate_agent_network_report(payload)


@router.post("/reports/aml", response_model=ReportResponse)
def generate_aml_report(payload: AMLReportRequest, svc: CBNComplianceService = Depends(get_svc)):
    """Generate Anti-Money Laundering (AML) Report."""
    return svc.generate_aml_report(payload)


@router.post("/reports/kyc-compliance", response_model=ReportResponse)
def generate_kyc_report(payload: KYCComplianceRequest, svc: CBNComplianceService = Depends(get_svc)):
    """Generate KYC Compliance Report with tiered customer data."""
    return svc.generate_kyc_compliance_report(payload)


@router.post("/sar", summary="File a Suspicious Activity Report")
def file_sar(payload: SARRequest, svc: CBNComplianceService = Depends(get_svc)):
    """File a SAR with NFIU — must be submitted within 3 working days."""
    sar = svc.file_sar(payload)
    return {"sar_id": sar.id, "reference_number": sar.reference_number, "status": "FILED"}


@router.get("/reports/pending", response_model=List[ReportResponse])
def get_pending_reports(svc: CBNComplianceService = Depends(get_svc)):
    """List all reports awaiting submission to CBN."""
    return svc.get_pending_reports()


@router.post("/reports/{report_id}/submit", response_model=ReportResponse)
def submit_report(report_id: str, submission_reference: str = Query(...), svc: CBNComplianceService = Depends(get_svc)):
    """Mark a report as submitted to the CBN portal."""
    try:
        return svc.submit_report(report_id, submission_reference)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reports/{report_id}/acknowledge", response_model=ReportResponse)
def acknowledge_report(report_id: str, cbn_reference: str = Query(...), svc: CBNComplianceService = Depends(get_svc)):
    """Record CBN acknowledgement of a submitted report."""
    try:
        return svc.acknowledge_report(report_id, cbn_reference)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/{report_id}/export/csv", response_class=PlainTextResponse)
def export_report_csv(report_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Export a report as CSV for CBN portal upload."""
    try:
        return svc.export_report_csv(report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/calendar/{year}")
def get_reporting_calendar(year: int, svc: CBNComplianceService = Depends(get_svc)):
    """Get the full CBN regulatory reporting calendar for a given year."""
    return svc.get_report_calendar(year)


@router.get("/health")
def health():
    return {"status": "ok", "service": "cbn-compliance-comprehensive"}
