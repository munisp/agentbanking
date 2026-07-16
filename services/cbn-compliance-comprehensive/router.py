"""CBN Comprehensive Compliance Reports — API Router"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
from service import (
    CBNComplianceService, MonthlyActivityRequest, QuarterlyFraudRequest,
    CTRRequest, SARRequest, AgentNetworkRequest, AMLReportRequest,
    KYCComplianceRequest, ReportResponse, ReportType,
    CreateFilingRequest, CreateKYCRecordRequest, UpdateKYCRecordRequest,
    AddKYCDocumentRequest, AddKYCCheckRequest, RetentionPolicy,
)
from config import get_db

router = APIRouter(tags=["CBN Compliance"])


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


@router.get("/api/v1/sandbox/experiments")
def get_sandbox_experiments(svc: CBNComplianceService = Depends(get_svc)):
    """List all compliance sandbox experiments."""
    experiments = svc.list_sandbox_experiments()
    return {"experiments": experiments, "total": len(experiments), "status": "active"}


@router.post("/api/v1/sandbox/experiments")
def create_sandbox_experiment(
    payload: Dict[str, Any] = Body(default={}),
    svc: CBNComplianceService = Depends(get_svc),
):
    """Create a new compliance sandbox experiment."""
    if not payload.get("name"):
        raise HTTPException(status_code=422, detail="name is required")
    return svc.create_sandbox_experiment(payload)


@router.post("/api/v1/sandbox/experiments/{experiment_id}/launch")
def launch_sandbox_experiment(experiment_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Launch a sandbox experiment (moves status to running)."""
    try:
        return svc.launch_sandbox_experiment(experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/sandbox/experiments/{experiment_id}/stop")
def stop_sandbox_experiment(experiment_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Stop a running sandbox experiment (moves status to completed)."""
    try:
        return svc.stop_sandbox_experiment(experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# Dashboard endpoints (called by admin UI)
# ─────────────────────────────────────────────

@router.get("/api/v1/automation/dashboard")
def automation_dashboard(svc: CBNComplianceService = Depends(get_svc)):
    return svc.get_automation_dashboard()


# ─────────────────────────────────────────────
# Compliance Audits CRUD
# ─────────────────────────────────────────────

@router.get("/api/v1/audits")
def list_audits(status: Optional[str] = Query(None), svc: CBNComplianceService = Depends(get_svc)):
    return {"audits": svc.list_audits(status=status)}


@router.post("/api/v1/audits")
def create_audit(payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    if not payload.get("framework") or not payload.get("scheduledDate") or not payload.get("auditor"):
        raise HTTPException(status_code=422, detail="framework, scheduledDate, and auditor are required")
    return svc.create_audit(payload)


@router.patch("/api/v1/audits/{audit_id}")
def update_audit(audit_id: str, payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.update_audit(audit_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/api/v1/audits/{audit_id}")
def delete_audit(audit_id: str, svc: CBNComplianceService = Depends(get_svc)):
    try:
        svc.delete_audit(audit_id)
        return {"message": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# Compliance Policies CRUD
# ─────────────────────────────────────────────

@router.get("/api/v1/policies")
def list_policies(status: Optional[str] = Query(None), svc: CBNComplianceService = Depends(get_svc)):
    return {"policies": svc.list_policies(status=status)}


@router.post("/api/v1/policies")
def create_policy(payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    if not payload.get("name"):
        raise HTTPException(status_code=422, detail="name is required")
    return svc.create_policy(payload)


@router.patch("/api/v1/policies/{policy_id}")
def update_policy(policy_id: str, payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.update_policy(policy_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/api/v1/policies/{policy_id}")
def delete_policy(policy_id: str, svc: CBNComplianceService = Depends(get_svc)):
    try:
        svc.delete_policy(policy_id)
        return {"message": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# Framework score update (admin-driven)
# ─────────────────────────────────────────────

@router.patch("/api/v1/frameworks/{framework_id}/score")
def update_framework_score(framework_id: str, payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.update_framework_score(framework_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/v1/reports/dashboard")
def reports_dashboard(svc: CBNComplianceService = Depends(get_svc)):
    return svc.get_reports_dashboard_enriched()


# ─────────────────────────────────────────────
# Compliance Filing endpoints
# ─────────────────────────────────────────────

@router.get("/api/v1/filings/stats")
def filing_stats(svc: CBNComplianceService = Depends(get_svc)):
    return svc.get_filing_stats()


@router.get("/api/v1/filings")
def list_filings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: CBNComplianceService = Depends(get_svc),
):
    return svc.list_filings(skip=skip, limit=limit)


@router.post("/api/v1/filings")
def create_filing(payload: CreateFilingRequest, svc: CBNComplianceService = Depends(get_svc)):
    return svc.create_filing(payload)


@router.post("/api/v1/filings/{filing_id}/submit")
def submit_compliance_filing(filing_id: str, svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.submit_compliance_filing(filing_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# Compliance Training endpoints
# ─────────────────────────────────────────────

@router.get("/api/v1/training/dashboard")
def training_dashboard(svc: CBNComplianceService = Depends(get_svc)):
    return svc.get_training_dashboard_live()


@router.get("/api/v1/training/tracker")
def training_tracker(svc: CBNComplianceService = Depends(get_svc)):
    return svc.get_training_tracker()


@router.get("/api/v1/certs/dashboard")
def cert_dashboard(svc: CBNComplianceService = Depends(get_svc)):
    return svc.get_cert_dashboard()


# ─────────────────────────────────────────────
# KYC Record endpoints (served under /compliance-kyc/* route)
# ─────────────────────────────────────────────

@router.get("/records")
def list_kyc_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: CBNComplianceService = Depends(get_svc),
):
    return svc.list_kyc_records(skip=skip, limit=limit)


@router.post("/records")
def create_kyc_record(payload: CreateKYCRecordRequest, svc: CBNComplianceService = Depends(get_svc)):
    return svc.create_kyc_record(payload)


@router.get("/records/{record_id}")
def get_kyc_record(record_id: str, svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.get_kyc_record(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/records/{record_id}")
def update_kyc_record(record_id: str, payload: UpdateKYCRecordRequest, svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.update_kyc_record(record_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/records/{record_id}/documents")
def add_kyc_document(record_id: str, payload: AddKYCDocumentRequest, svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.add_kyc_document(record_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/records/{record_id}/checks")
def add_kyc_check(record_id: str, payload: AddKYCCheckRequest, svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.add_kyc_check(record_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# CBN Reports Schedule endpoints
# ─────────────────────────────────────────────

@router.get("/api/v1/cbn-reports/schedules")
def get_cbn_reports_schedules(svc: CBNComplianceService = Depends(get_svc)):
    """List persisted CBN report schedules (seeded with defaults on first call)."""
    schedules = svc.list_report_schedules()
    return {"schedules": schedules, "total": len(schedules)}


@router.post("/api/v1/cbn-reports/{schedule_id}/run")
def run_cbn_report_schedule(schedule_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Trigger an immediate run of a CBN report schedule."""
    try:
        return svc.run_report_schedule(schedule_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/cbn-reports/schedules")
def create_cbn_report_schedule(
    payload: Dict[str, Any] = Body(default={}),
    svc: CBNComplianceService = Depends(get_svc),
):
    """Create a new CBN report schedule."""
    if not payload.get("name"):
        raise HTTPException(status_code=422, detail="name is required")
    if payload.get("frequency") not in ("daily", "weekly", "monthly", "quarterly"):
        raise HTTPException(status_code=422, detail="frequency must be daily, weekly, monthly, or quarterly")
    return svc.create_report_schedule(payload)


@router.delete("/api/v1/cbn-reports/schedules/{schedule_id}")
def delete_cbn_report_schedule(schedule_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Delete a CBN report schedule."""
    try:
        svc.delete_report_schedule(schedule_id)
        return {"message": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/api/v1/cbn-reports/{schedule_id}/status")
def update_cbn_report_schedule_status(
    schedule_id: str,
    payload: Dict[str, Any] = Body(default={}),
    svc: CBNComplianceService = Depends(get_svc),
):
    """Update the status (active/paused/failed) of a CBN report schedule."""
    status = payload.get("status")
    if not status:
        raise HTTPException(status_code=422, detail="status field required")
    try:
        return svc.update_report_schedule_status(schedule_id, status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────
# NFIU Reports endpoints
# ─────────────────────────────────────────────

@router.get("/api/v1/nfiu-reports")
def get_nfiu_reports(
    status: Optional[str] = Query(None, description="Filter by status: filed, pending, rejected"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    svc: CBNComplianceService = Depends(get_svc)
):
    """Get Nigerian Financial Intelligence Unit (NFIU) reports list."""
    try:
        reports = svc.get_nfiu_reports(status=status, skip=skip, limit=limit)
        return {
            "nfiu_reports": reports if isinstance(reports, list) else [],
            "total": len(reports) if isinstance(reports, list) else 0,
            "skip": skip,
            "limit": limit,
            "filters": {"status": status}
        }
    except Exception as e:
        logger.error(f"Error fetching NFIU reports: {e}")
        return {
            "nfiu_reports": [],
            "total": 0,
            "skip": skip,
            "limit": limit,
            "filters": {"status": status}
        }


@router.get("/api/v1/nfiu-reports/{report_id}")
def get_nfiu_report_detail(report_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Get detailed NFIU report with all submissions and history."""
    try:
        report = svc.get_nfiu_report_detail(report_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/nfiu-reports/{report_id}/submit")
def submit_to_nfiu(report_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Submit a report to NFIU portal."""
    try:
        result = svc.submit_nfiu_report(report_id)
        return {
            "report_id": report_id,
            "status": "submitted",
            "nfiu_reference": result.get("nfiu_reference", ""),
            "submitted_at": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


COMPLIANCE_KB = [
    {"id": "kb1", "title": "CBN Agent Banking Guidelines 2023", "category": "CBN", "relevance": 0.95, "content": "CBN circular outlining agent banking requirements, float limits, and POS terminal management guidelines."},
    {"id": "kb2", "title": "KYC Tiered Framework", "category": "KYC", "relevance": 0.87, "content": "Three-tier KYC system: Tier 1 (BVN only), Tier 2 (BVN + address), Tier 3 (full documentation)."},
    {"id": "kb3", "title": "AML/CFT Compliance Manual", "category": "AML", "relevance": 0.82, "content": "Anti-Money Laundering procedures, STR filing requirements, and suspicious transaction identification."},
    {"id": "kb4", "title": "Data Retention Policy — CBN Directive", "category": "NDPR", "relevance": 0.78, "content": "Mandatory data retention periods: transactions 7 years, KYC docs 5 years, audit logs 10 years."},
    {"id": "kb5", "title": "NFIU SAR Reporting Procedure", "category": "NFIU", "relevance": 0.74, "content": "Suspicious Activity Reports must be filed with NFIU within 3 working days of detection."},
]


@router.get("/api/v1/retention-policies")
def get_retention_policies(svc: CBNComplianceService = Depends(get_svc)):
    return svc.list_retention_policies()


@router.post("/api/v1/retention-policies/{policy_id}/enforce")
def enforce_retention_policy(policy_id: str, svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.enforce_retention_policy(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/api/v1/retention-policies/{policy_id}")
def update_retention_policy(policy_id: str, payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    try:
        return svc.update_retention_policy(policy_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/chatbot/message")
def chatbot_message(payload: Dict[str, Any] = Body(default={})):
    user_msg = payload.get("message", "").lower()
    replies = {
        "kyc": "KYC requirements: Tier 1 requires BVN only (₦50k/day limit). Tier 2 requires BVN + utility bill (₦200k/day). Tier 3 requires full documentation including NIN (₦5M/day).",
        "aml": "AML compliance: All transactions ≥ ₦5M require CTR filing. Suspicious transactions must be reported to NFIU within 3 working days via SAR.",
        "cbn": "CBN agent banking guidelines require all agents to have CAC registration, maintain float within approved limits, and submit monthly activity reports by the 10th of the following month.",
        "agent": "Agent onboarding requires: CAC registration, guarantor documentation, physical verification, and completion of CBN-approved agent training.",
        "report": "Mandatory reports: Monthly Activity Report (due 10th), Quarterly Fraud Report (due 15th of following month), Annual KYC Compliance Report.",
    }
    for key, reply in replies.items():
        if key in user_msg:
            return {"reply": reply}
    return {"reply": "I can help with CBN regulations, KYC requirements, AML compliance, agent onboarding, and reporting obligations. Please ask a specific question."}


@router.get("/api/v1/knowledge-base/search")
def search_knowledge_base(q: str = Query(""), topK: int = Query(5)):
    q_lower = q.lower()
    results = [
        r for r in COMPLIANCE_KB
        if not q_lower or any(w in r["title"].lower() or w in r["content"].lower() for w in q_lower.split())
    ][:topK]
    return {"results": results or COMPLIANCE_KB[:topK], "query": q, "total": len(results or COMPLIANCE_KB[:topK])}


@router.get("/health")
def health():
    return {"status": "ok", "service": "cbn-compliance-comprehensive"}


# ─────────────────────────────────────────────
# GDPR / NDPR data subject request endpoints
# Served at /gdpr/api/v1/* — APISIX routes /gdpr/* here without stripping prefix
# ─────────────────────────────────────────────

@router.get("/gdpr/api/v1/requests")
def list_gdpr_requests(
    status: Optional[str] = Query(None, description="Filter by status: pending, in_progress, completed, rejected"),
    svc: CBNComplianceService = Depends(get_svc),
):
    """List all GDPR/NDPR data subject requests."""
    return svc.list_gdpr_requests(status=status)


@router.post("/gdpr/api/v1/requests")
def create_gdpr_request(
    payload: Dict[str, Any] = Body(default={}),
    svc: CBNComplianceService = Depends(get_svc),
):
    """Create a new GDPR/NDPR data subject request."""
    if not payload.get("subject_name") or not payload.get("subject_email"):
        raise HTTPException(status_code=422, detail="subject_name and subject_email are required")
    return svc.create_gdpr_request(payload)


@router.patch("/gdpr/api/v1/requests/{request_id}")
def update_gdpr_request(
    request_id: str,
    payload: Dict[str, Any] = Body(default={}),
    svc: CBNComplianceService = Depends(get_svc),
):
    """Update the status or notes of a GDPR/NDPR request."""
    try:
        return svc.update_gdpr_request(request_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/gdpr/api/v1/requests/{request_id}/export")
def export_gdpr_request(request_id: str, svc: CBNComplianceService = Depends(get_svc)):
    """Export the data for a GDPR/NDPR subject request."""
    try:
        return svc.export_gdpr_request(request_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# Agent-facing compliance check endpoints
# ─────────────────────────────────────────────

@router.get("/api/v1/regulatory-compliance/checks")
def get_regulatory_compliance_checks(svc: CBNComplianceService = Depends(get_svc)):
    """Actionable compliance checks for agent-facing view (AML, KYC, CTR, SAR, filings)."""
    return svc.get_compliance_checks()


@router.post("/api/v1/regulatory-compliance/run")
def run_regulatory_compliance_checks(svc: CBNComplianceService = Depends(get_svc)):
    """Re-evaluate all compliance checks and return refreshed results."""
    return svc.get_compliance_checks()


@router.get("/api/v1/regulatory-report-generator/stats")
def get_regulatory_report_generator_stats(svc: CBNComplianceService = Depends(get_svc)):
    """Stats for the regulatory report generator dashboard (agent-facing)."""
    return svc.get_regulatory_report_generator_stats()


@router.get("/api/v1/regulatory-reporting-engine/stats")
def get_regulatory_reporting_engine_stats(svc: CBNComplianceService = Depends(get_svc)):
    """Stats for the regulatory reporting engine page."""
    return svc.get_regulatory_reporting_engine_stats()


@router.get("/api/v1/regulatory-filing-automation/stats")
def get_regulatory_filing_automation_stats(svc: CBNComplianceService = Depends(get_svc)):
    """Stats for the regulatory filing automation page."""
    return svc.get_regulatory_filing_automation_stats()


# ─────────────────────────────────────────────
# Ingest endpoints — called by internal services
# ─────────────────────────────────────────────

@router.post("/api/v1/ctr-ingest")
def ingest_ctr_record(payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    """
    Receive a completed transaction >= NGN 5M from payment-processing-service.
    Creates a CTRRecord for inclusion in the next Currency Transaction Report.
    Expected fields: transaction_id, amount (NGN float), transaction_type, agent_id,
    customer_name, customer_bvn, customer_account, transaction_date (ISO).
    """
    if not payload.get("transaction_id"):
        raise HTTPException(status_code=422, detail="transaction_id is required")
    return svc.ingest_ctr_record(payload)


@router.post("/api/v1/fraud-ingest")
def ingest_fraud_record(payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    """
    Receive a fraud event from fraud-engine when a transaction is blocked or flagged.
    Creates a FraudRecord that feeds into the Quarterly Fraud & Forgeries Report.
    Expected fields: fraud_type, amount_attempted, channel, incident_date (ISO),
    victim_account, perpetrator_info.
    """
    return svc.ingest_fraud_record(payload)


@router.post("/api/v1/kyc-ingest")
def ingest_kyc_update(payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    """
    Receive a KYC status change from agent-service.
    Creates or updates the compliance KYC record for the agent.
    Expected fields: agent_id (str), kyc_status (not_verified|pending|verified|failed_verification), tenant_id.
    """
    if not payload.get("agent_id"):
        raise HTTPException(status_code=422, detail="agent_id is required")
    try:
        return svc.ingest_kyc_update(payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/api/v1/kyc/summary")
def get_kyc_summary(svc: CBNComplianceService = Depends(get_svc)):
    """
    Aggregated KYC compliance summary for the admin dashboard.
    Returns total/approved/pending/rejected counts, compliance rate, BVN stats, and document counts.
    """
    return svc.get_kyc_summary()


@router.post("/api/v1/agent-stats/record")
def record_agent_transaction(payload: Dict[str, Any] = Body(default={}), svc: CBNComplianceService = Depends(get_svc)):
    """
    Receive a completed transaction from payment-processing-service.
    Upserts the AgentNetworkReport for the current month so Monthly Activity
    Reports reflect live data without manual aggregation.
    Expected fields: transaction_type, amount_ngn (float), period (YYYY-MM, optional).
    """
    return svc.record_agent_transaction(payload)
