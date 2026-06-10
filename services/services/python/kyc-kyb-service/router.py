"""
KYC-KYB Service Router
Exposes continuous monitoring, case management, and related modules via FastAPI endpoints.
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .continuous_monitoring import (
    get_continuous_monitoring_service,
    RiskLevel,
    AlertType,
    ScreeningType,
    ScreeningProvider,
    MonitoringStatus,
)
from .case_management import (
    get_case_management_service,
    CaseType,
    CaseStatus,
    Priority,
    EscalationReason,
    QAResult,
    Reviewer,
    ReviewerRole,
    ReviewerSkill,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kyc-kyb", tags=["kyc-kyb"])


class EnrollSubjectRequest(BaseModel):
    subject_id: str
    subject_type: str
    name: str
    initial_risk_level: str
    initial_risk_score: float
    risk_factors: Dict[str, float]
    metadata: Optional[Dict[str, Any]] = None


class ProcessEventRequest(BaseModel):
    subject_id: str
    event_type: str
    event_data: Dict[str, Any]


class AcknowledgeAlertRequest(BaseModel):
    alert_id: str
    acknowledged_by: str


class ResolveAlertRequest(BaseModel):
    alert_id: str
    resolved_by: str
    case_id: Optional[str] = None


class CreateCaseRequest(BaseModel):
    case_type: str
    priority: str
    subject_id: str
    subject_type: str
    title: str
    description: str
    created_by: str
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    auto_assign: bool = True


class UpdateCaseStatusRequest(BaseModel):
    status: str
    updated_by: str
    notes: Optional[str] = None


class ResolveCaseRequest(BaseModel):
    decision: str
    resolution_notes: str
    resolved_by: str


class EscalateCaseRequest(BaseModel):
    reason: str
    escalated_by: str
    notes: Optional[str] = None


class AddCaseNoteRequest(BaseModel):
    author: str
    content: str
    note_type: str = "general"


class RegisterReviewerRequest(BaseModel):
    reviewer_id: str
    name: str
    email: str
    role: str
    skills: List[str]
    max_workload: int = 20


class QAReviewRequest(BaseModel):
    qa_reviewer_id: str
    result: str
    score: float
    findings: List[str]
    recommendations: List[str]


class RegisterBusinessRequest(BaseModel):
    business_id: str
    cac_number: str
    business_name: str
    directors: List[str]
    shareholders: List[Dict[str, Any]]


@router.post("/monitoring/enroll")
async def enroll_subject(request: EnrollSubjectRequest):
    svc = get_continuous_monitoring_service()
    try:
        risk_level = RiskLevel(request.initial_risk_level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid risk level: {request.initial_risk_level}")
    subject = await svc.enroll_subject(
        subject_id=request.subject_id,
        subject_type=request.subject_type,
        name=request.name,
        initial_risk_level=risk_level,
        initial_risk_score=request.initial_risk_score,
        risk_factors=request.risk_factors,
        metadata=request.metadata,
    )
    return {"subject_id": subject.subject_id, "status": subject.status.value, "risk_level": subject.risk_level.value}


@router.get("/monitoring/subjects/{subject_id}")
async def get_subject(subject_id: str):
    svc = get_continuous_monitoring_service()
    subject = svc.get_subject(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {
        "subject_id": subject.subject_id,
        "name": subject.name,
        "subject_type": subject.subject_type,
        "risk_level": subject.risk_level.value,
        "status": subject.status.value,
        "enrolled_at": subject.enrolled_at.isoformat(),
        "last_activity": subject.last_activity.isoformat(),
    }


@router.post("/monitoring/screening/{subject_id}")
async def run_screening(subject_id: str):
    svc = get_continuous_monitoring_service()
    try:
        results = await svc.run_scheduled_screening(subject_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "subject_id": subject_id,
        "results_count": len(results),
        "matches": [{"result_id": r.result_id, "is_match": r.is_match, "match_score": r.match_score} for r in results],
    }


@router.post("/monitoring/events")
async def process_event(request: ProcessEventRequest):
    svc = get_continuous_monitoring_service()
    try:
        alerts = await svc.process_event(request.subject_id, request.event_type, request.event_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "subject_id": request.subject_id,
        "alerts_triggered": len(alerts),
        "alerts": [{"alert_id": a.alert_id, "alert_type": a.alert_type.value, "severity": a.severity.value} for a in alerts],
    }


@router.get("/monitoring/alerts")
async def get_alerts(
    subject_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    unresolved_only: bool = False,
):
    svc = get_continuous_monitoring_service()
    at = AlertType(alert_type) if alert_type else None
    sv = RiskLevel(severity) if severity else None
    alerts = svc.get_alerts(subject_id=subject_id, alert_type=at, severity=sv, unresolved_only=unresolved_only)
    return {
        "count": len(alerts),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "subject_id": a.subject_id,
                "alert_type": a.alert_type.value,
                "severity": a.severity.value,
                "title": a.title,
                "description": a.description,
                "created_at": a.created_at.isoformat(),
                "acknowledged": a.acknowledged,
                "resolved": a.resolved,
            }
            for a in alerts
        ],
    }


@router.post("/monitoring/alerts/acknowledge")
async def acknowledge_alert(request: AcknowledgeAlertRequest):
    svc = get_continuous_monitoring_service()
    try:
        alert = await svc.acknowledge_alert(request.alert_id, request.acknowledged_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"alert_id": alert.alert_id, "acknowledged": alert.acknowledged}


@router.post("/monitoring/alerts/resolve")
async def resolve_alert(request: ResolveAlertRequest):
    svc = get_continuous_monitoring_service()
    try:
        alert = await svc.resolve_alert(request.alert_id, request.resolved_by, request.case_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"alert_id": alert.alert_id, "resolved": alert.resolved}


@router.post("/monitoring/risk-decay")
async def check_risk_decay():
    svc = get_continuous_monitoring_service()
    alerts = await svc.check_risk_score_decay()
    return {"alerts_generated": len(alerts)}


@router.post("/monitoring/corporate/register")
async def register_business(request: RegisterBusinessRequest):
    svc = get_continuous_monitoring_service()
    svc.corporate_monitoring.register_business(
        business_id=request.business_id,
        cac_number=request.cac_number,
        business_name=request.business_name,
        directors=request.directors,
        shareholders=request.shareholders,
    )
    return {"business_id": request.business_id, "status": "registered"}


@router.post("/monitoring/corporate/{business_id}/check")
async def check_corporate_status(business_id: str):
    svc = get_continuous_monitoring_service()
    try:
        changes = await svc.corporate_monitoring.check_corporate_status(business_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "business_id": business_id,
        "changes_detected": len(changes),
        "changes": [{"type": ct.value, "details": d} for ct, d in changes],
    }


@router.post("/cases")
async def create_case(request: CreateCaseRequest):
    svc = get_case_management_service()
    try:
        ct = CaseType(request.case_type)
        pr = Priority(request.priority)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    case = await svc.create_case(
        case_type=ct,
        priority=pr,
        subject_id=request.subject_id,
        subject_type=request.subject_type,
        title=request.title,
        description=request.description,
        created_by=request.created_by,
        metadata=request.metadata,
        tags=request.tags,
        auto_assign=request.auto_assign,
    )
    return {
        "case_id": case.case_id,
        "status": case.status.value,
        "assigned_to": case.assigned_to,
        "due_at": case.due_at.isoformat() if case.due_at else None,
    }


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    svc = get_case_management_service()
    case = await svc.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case_id": case.case_id,
        "case_type": case.case_type.value,
        "status": case.status.value,
        "priority": case.priority.value,
        "subject_id": case.subject_id,
        "title": case.title,
        "description": case.description,
        "assigned_to": case.assigned_to,
        "created_at": case.created_at.isoformat(),
        "due_at": case.due_at.isoformat() if case.due_at else None,
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else None,
        "decision": case.decision,
        "notes": case.notes,
        "tags": case.tags,
    }


@router.get("/cases")
async def list_cases(
    status: Optional[str] = None,
    case_type: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    subject_id: Optional[str] = None,
    limit: int = Query(default=100, le=500),
):
    svc = get_case_management_service()
    cs = CaseStatus(status) if status else None
    ct = CaseType(case_type) if case_type else None
    pr = Priority(priority) if priority else None
    cases = await svc.get_cases(
        status=cs, case_type=ct, priority=pr, assigned_to=assigned_to, subject_id=subject_id, limit=limit
    )
    return {
        "count": len(cases),
        "cases": [
            {
                "case_id": c.case_id,
                "case_type": c.case_type.value,
                "status": c.status.value,
                "priority": c.priority.value,
                "title": c.title,
                "assigned_to": c.assigned_to,
                "created_at": c.created_at.isoformat(),
            }
            for c in cases
        ],
    }


@router.put("/cases/{case_id}/status")
async def update_case_status(case_id: str, request: UpdateCaseStatusRequest):
    svc = get_case_management_service()
    try:
        cs = CaseStatus(request.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        case = await svc.update_case_status(case_id, cs, request.updated_by, request.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"case_id": case.case_id, "status": case.status.value}


@router.post("/cases/{case_id}/resolve")
async def resolve_case(case_id: str, request: ResolveCaseRequest):
    svc = get_case_management_service()
    try:
        case = await svc.resolve_case(case_id, request.decision, request.resolution_notes, request.resolved_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "case_id": case.case_id,
        "status": case.status.value,
        "decision": case.decision,
        "sla_met": case.sla_resolution_met,
    }


@router.post("/cases/{case_id}/escalate")
async def escalate_case(case_id: str, request: EscalateCaseRequest):
    svc = get_case_management_service()
    try:
        reason = EscalationReason(request.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        case = await svc.escalate_case(case_id, reason, request.escalated_by, request.notes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"case_id": case.case_id, "status": case.status.value, "escalated_to": case.escalated_to}


@router.post("/cases/{case_id}/notes")
async def add_case_note(case_id: str, request: AddCaseNoteRequest):
    svc = get_case_management_service()
    try:
        case = await svc.add_case_note(case_id, request.author, request.content, request.note_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"case_id": case.case_id, "notes_count": len(case.notes)}


@router.get("/cases/metrics")
async def get_case_metrics():
    svc = get_case_management_service()
    metrics = await svc.get_metrics()
    return asdict(metrics)


@router.post("/cases/sla-check")
async def check_sla_breaches():
    svc = get_case_management_service()
    breached = await svc.check_sla_breaches()
    return {"breached_count": len(breached), "case_ids": [c.case_id for c in breached]}


@router.post("/reviewers")
async def register_reviewer(request: RegisterReviewerRequest):
    svc = get_case_management_service()
    try:
        role = ReviewerRole(request.role)
        skills = [ReviewerSkill(s) for s in request.skills]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    reviewer = Reviewer(
        reviewer_id=request.reviewer_id,
        name=request.name,
        email=request.email,
        role=role,
        skills=skills,
        max_workload=request.max_workload,
    )
    svc.register_reviewer(reviewer)
    return {"reviewer_id": reviewer.reviewer_id, "role": reviewer.role.value}


@router.post("/cases/{case_id}/qa")
async def create_qa_review(case_id: str, request: QAReviewRequest):
    svc = get_case_management_service()
    case = await svc.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        result = QAResult(request.result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    qa = svc._qa_manager.create_qa_review(
        case=case,
        qa_reviewer_id=request.qa_reviewer_id,
        result=result,
        score=request.score,
        findings=request.findings,
        recommendations=request.recommendations,
    )
    return {"qa_id": qa.qa_id, "result": qa.result.value, "score": qa.score}


class DeepKYBVerifyRequest(BaseModel):
    business_name: str
    business_type: str = "llc"
    verification_path: str = "standard"
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    shareholders: Optional[List[Dict[str, Any]]] = None
    directors: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class BankStatementSubmitRequest(BaseModel):
    verification_id: str
    transactions: List[Dict[str, Any]]
    account_number: str
    bank_name: str
    period_start: str
    period_end: str


class EvidenceSubmitRequest(BaseModel):
    verification_id: str
    document_type: str
    document_data: Dict[str, Any]
    document_date: str


class CompleteVerificationRequest(BaseModel):
    reviewer_id: str


@router.post("/deep-kyb/verify")
async def deep_kyb_verify(request: DeepKYBVerifyRequest):
    from .deep_kyb import get_deep_kyb_service, BusinessType, VerificationPath as VPath
    svc = get_deep_kyb_service()
    try:
        btype = BusinessType(request.business_type)
    except ValueError:
        btype = BusinessType.LLC
    try:
        vpath = VPath(request.verification_path)
    except ValueError:
        vpath = VPath.STANDARD

    import secrets
    business_id = secrets.token_hex(16)
    verification = await svc.start_verification(
        business_id=business_id,
        business_name=request.business_name,
        business_type=btype,
        verification_path=vpath,
        cac_number=request.registration_number,
        tin=request.tax_id,
        shareholders=request.shareholders,
        directors=request.directors,
        metadata=request.metadata,
    )
    return {
        "verification_id": verification.verification_id,
        "business_id": verification.business_id,
        "status": verification.status.value,
        "risk_level": verification.risk_level.value,
        "verification_path": verification.verification_path.value,
        "created_at": verification.created_at.isoformat(),
    }


@router.get("/deep-kyb/status/{verification_id}")
async def deep_kyb_status(verification_id: str):
    from .deep_kyb import get_deep_kyb_service
    svc = get_deep_kyb_service()
    verification = svc.get_verification(verification_id)
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    from dataclasses import asdict as _asdict
    bs = None
    if verification.bank_statement_analysis:
        bs = {
            "statement_id": verification.bank_statement_analysis.statement_id,
            "cash_flow_score": verification.bank_statement_analysis.cash_flow_score,
            "volatility_score": verification.bank_statement_analysis.volatility_score,
            "consistency_score": verification.bank_statement_analysis.consistency_score,
            "overall_health_score": verification.bank_statement_analysis.overall_health_score,
            "red_flags": verification.bank_statement_analysis.red_flags,
        }
    return {
        "verification_id": verification.verification_id,
        "business_id": verification.business_id,
        "business_name": verification.business_name,
        "status": verification.status.value,
        "risk_level": verification.risk_level.value,
        "risk_score": verification.risk_score,
        "verification_path": verification.verification_path.value,
        "bank_statement_analysis": bs,
        "evidence_count": len(verification.evidence_documents),
        "ubo_count": len(verification.corporate_structure.beneficial_owners),
        "director_count": len(verification.corporate_structure.directors),
        "created_at": verification.created_at.isoformat(),
        "updated_at": verification.updated_at.isoformat(),
    }


@router.post("/deep-kyb/bank-statement")
async def deep_kyb_bank_statement(request: BankStatementSubmitRequest):
    from .deep_kyb import get_deep_kyb_service
    svc = get_deep_kyb_service()
    try:
        analysis = await svc.submit_bank_statement(
            verification_id=request.verification_id,
            transactions=request.transactions,
            account_number=request.account_number,
            bank_name=request.bank_name,
            period_start=datetime.fromisoformat(request.period_start),
            period_end=datetime.fromisoformat(request.period_end),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "statement_id": analysis.statement_id,
        "cash_flow_score": analysis.cash_flow_score,
        "volatility_score": analysis.volatility_score,
        "consistency_score": analysis.consistency_score,
        "overall_health_score": analysis.overall_health_score,
        "transaction_count": analysis.transaction_count,
        "total_credits": analysis.total_credits,
        "total_debits": analysis.total_debits,
        "revenue_trend": analysis.revenue_trend,
        "red_flags": analysis.red_flags,
        "insights": analysis.insights,
    }


@router.post("/deep-kyb/evidence")
async def deep_kyb_evidence(request: EvidenceSubmitRequest):
    from .deep_kyb import get_deep_kyb_service, DocumentType as DType
    svc = get_deep_kyb_service()
    try:
        dtype = DType(request.document_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid document type: {request.document_type}")
    try:
        evidence = await svc.submit_evidence(
            verification_id=request.verification_id,
            document_type=dtype,
            document_data=request.document_data,
            document_date=datetime.fromisoformat(request.document_date),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "evidence_id": evidence.evidence_id,
        "document_type": evidence.document_type.value,
        "confidence_score": evidence.confidence_score,
        "verified": evidence.verified,
    }


@router.post("/deep-kyb/verify-owners/{verification_id}")
async def deep_kyb_verify_owners(verification_id: str):
    from .deep_kyb import get_deep_kyb_service
    svc = get_deep_kyb_service()
    try:
        results = await svc.verify_beneficial_owners(verification_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "verification_id": verification_id,
        "owners": [
            {
                "owner_id": owner.owner_id,
                "name": owner.name,
                "ownership_percentage": owner.ownership_percentage,
                "is_pep": owner.is_pep,
                "is_sanctioned": owner.is_sanctioned,
                "passed": passed,
                "details": details,
            }
            for owner, passed, details in results
        ],
    }


@router.post("/deep-kyb/verify-directors/{verification_id}")
async def deep_kyb_verify_directors(verification_id: str):
    from .deep_kyb import get_deep_kyb_service
    svc = get_deep_kyb_service()
    try:
        results = await svc.verify_directors(verification_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "verification_id": verification_id,
        "directors": [
            {
                "director_id": director.director_id,
                "name": director.name,
                "position": director.position,
                "passed": passed,
                "details": details,
            }
            for director, passed, details in results
        ],
    }


@router.post("/deep-kyb/complete/{verification_id}")
async def deep_kyb_complete(verification_id: str, request: CompleteVerificationRequest):
    from .deep_kyb import get_deep_kyb_service
    svc = get_deep_kyb_service()
    try:
        verification = await svc.complete_verification(verification_id, request.reviewer_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "verification_id": verification.verification_id,
        "status": verification.status.value,
        "risk_score": verification.risk_score,
        "risk_level": verification.risk_level.value,
        "risk_factors": verification.risk_factors,
        "approved_at": verification.approved_at.isoformat() if verification.approved_at else None,
        "rejection_reason": verification.rejection_reason,
    }


@router.get("/deep-kyb/paths")
async def deep_kyb_paths():
    from .deep_kyb import PATH_REQUIREMENTS
    return {
        path.value: {
            "description": config.get("description", ""),
            "required_documents": [d.value for d in config.get("required_documents", [])],
            "ubo_verification": config.get("ubo_verification", False),
            "director_verification": config.get("director_verification", False),
            "bank_statement_months": config.get("bank_statement_months", 0),
        }
        for path, config in PATH_REQUIREMENTS.items()
    }


@router.get("/health")
async def health():
    return {"service": "kyc-kyb-service", "status": "healthy", "timestamp": datetime.utcnow().isoformat()}
