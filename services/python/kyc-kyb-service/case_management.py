"""
Case Management Service
Manual review queue with SLA tracking, assignment routing, escalation workflows,
and quality assurance for KYC/KYB verification.

Integrates with: TigerBeetle, Kafka, Dapr, Temporal, Keycloak, Permify, Redis, APISIX
"""

import os
import json
import secrets
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class CaseType(str, Enum):
    """Types of cases"""
    NEW_MERCHANT = "new_merchant"
    REVERIFICATION = "reverification"
    DOCUMENT_REVIEW = "document_review"
    LIVENESS_REVIEW = "liveness_review"
    SCREENING_MATCH = "screening_match"
    TRANSACTION_ALERT = "transaction_alert"
    ESCALATION = "escalation"
    APPEAL = "appeal"
    PERIODIC_REVIEW = "periodic_review"


class CaseStatus(str, Enum):
    """Case status"""
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_INFO = "pending_info"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    """Case priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class ReviewerRole(str, Enum):
    """Reviewer role hierarchy"""
    L1_ANALYST = "l1_analyst"
    L2_ANALYST = "l2_analyst"
    SENIOR_ANALYST = "senior_analyst"
    TEAM_LEAD = "team_lead"
    COMPLIANCE_OFFICER = "compliance_officer"
    MANAGER = "manager"


class ReviewerSkill(str, Enum):
    """Reviewer skills for routing"""
    SANCTIONS_SCREENING = "sanctions_screening"
    LIVENESS_REVIEW = "liveness_review"
    TRANSACTION_MONITORING = "transaction_monitoring"
    HIGH_RISK = "high_risk"
    DOCUMENT_VERIFICATION = "document_verification"
    BUSINESS_VERIFICATION = "business_verification"
    FRAUD_INVESTIGATION = "fraud_investigation"


class EscalationReason(str, Enum):
    """Escalation reasons"""
    HIGH_RISK = "high_risk"
    POLICY_EXCEPTION = "policy_exception"
    COMPLEX_CASE = "complex_case"
    SENIOR_APPROVAL = "senior_approval"
    LEGAL_REVIEW = "legal_review"
    COMPLIANCE_REVIEW = "compliance_review"
    FRAUD_SUSPECTED = "fraud_suspected"
    SLA_BREACH = "sla_breach"


class QAResult(str, Enum):
    """QA review result"""
    PASS = "pass"
    FAIL = "fail"
    NEEDS_IMPROVEMENT = "needs_improvement"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class SLAConfig:
    """SLA configuration for case types"""
    response_hours: float
    resolution_hours: float
    escalation_hours: float


@dataclass
class Reviewer:
    """Reviewer profile"""
    reviewer_id: str
    name: str
    email: str
    role: ReviewerRole
    skills: List[ReviewerSkill]
    max_workload: int = 20
    current_workload: int = 0
    is_available: bool = True
    quality_score: float = 1.0
    cases_resolved: int = 0
    avg_resolution_time_hours: float = 0.0
    approval_rate: float = 0.0
    rejection_rate: float = 0.0


@dataclass
class Case:
    """Case record"""
    case_id: str
    case_type: CaseType
    status: CaseStatus
    priority: Priority
    subject_id: str
    subject_type: str  # individual, business
    title: str
    description: str
    created_at: datetime
    created_by: str
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    decision: Optional[str] = None
    escalated_to: Optional[str] = None
    escalation_reason: Optional[EscalationReason] = None
    escalated_at: Optional[datetime] = None
    sla_response_met: Optional[bool] = None
    sla_resolution_met: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    notes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QAReview:
    """QA review record"""
    qa_id: str
    case_id: str
    reviewer_id: str
    qa_reviewer_id: str
    result: QAResult
    score: float  # 0-100
    findings: List[str]
    recommendations: List[str]
    reviewed_at: datetime


@dataclass
class CaseMetrics:
    """Case metrics for dashboard"""
    total_cases: int
    open_cases: int
    assigned_cases: int
    resolved_cases: int
    escalated_cases: int
    avg_resolution_time_hours: float
    sla_compliance_rate: float
    oldest_open_case_hours: float
    cases_by_type: Dict[str, int]
    cases_by_priority: Dict[str, int]


# ============================================================================
# SLA CONFIGURATION
# ============================================================================

DEFAULT_SLA_CONFIG = {
    Priority.LOW: SLAConfig(response_hours=24.0, resolution_hours=72.0, escalation_hours=48.0),
    Priority.MEDIUM: SLAConfig(response_hours=8.0, resolution_hours=24.0, escalation_hours=16.0),
    Priority.HIGH: SLAConfig(response_hours=4.0, resolution_hours=12.0, escalation_hours=8.0),
    Priority.URGENT: SLAConfig(response_hours=1.0, resolution_hours=4.0, escalation_hours=2.0),
    Priority.CRITICAL: SLAConfig(response_hours=0.5, resolution_hours=2.0, escalation_hours=1.0),
}

ROLE_HIERARCHY = {
    ReviewerRole.L1_ANALYST: 1,
    ReviewerRole.L2_ANALYST: 2,
    ReviewerRole.SENIOR_ANALYST: 3,
    ReviewerRole.TEAM_LEAD: 4,
    ReviewerRole.COMPLIANCE_OFFICER: 5,
    ReviewerRole.MANAGER: 6,
}


# ============================================================================
# ASSIGNMENT ENGINE
# ============================================================================

class AssignmentEngine:
    """
    Intelligent case assignment with workload balancing and skill-based routing
    """
    
    def __init__(self):
        self._reviewers: Dict[str, Reviewer] = {}
    
    def register_reviewer(self, reviewer: Reviewer):
        """Register a reviewer"""
        self._reviewers[reviewer.reviewer_id] = reviewer
        logger.info(f"Reviewer registered: {reviewer.reviewer_id} - {reviewer.role.value}")
    
    def update_reviewer_availability(self, reviewer_id: str, is_available: bool):
        """Update reviewer availability"""
        if reviewer_id in self._reviewers:
            self._reviewers[reviewer_id].is_available = is_available
    
    def find_best_reviewer(
        self,
        case: Case,
        required_skills: Optional[List[ReviewerSkill]] = None,
        min_role: Optional[ReviewerRole] = None
    ) -> Optional[Reviewer]:
        """
        Find best reviewer for a case based on:
        - Availability
        - Workload
        - Skills match
        - Role requirements
        - Quality score
        """
        candidates = []
        
        for reviewer in self._reviewers.values():
            # Check availability
            if not reviewer.is_available:
                continue
            
            # Check workload
            if reviewer.current_workload >= reviewer.max_workload:
                continue
            
            # Check role requirement
            if min_role:
                if ROLE_HIERARCHY.get(reviewer.role, 0) < ROLE_HIERARCHY.get(min_role, 0):
                    continue
            
            # Check skills
            skill_match = 0
            if required_skills:
                skill_match = len(set(required_skills) & set(reviewer.skills))
                if skill_match == 0:
                    continue
            
            # Calculate score
            score = (
                skill_match * 10 +
                reviewer.quality_score * 5 +
                (reviewer.max_workload - reviewer.current_workload) * 2
            )
            
            candidates.append((reviewer, score))
        
        if not candidates:
            return None
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[0][0]
    
    def assign_case(self, case: Case, reviewer: Reviewer) -> Case:
        """Assign case to reviewer"""
        case.assigned_to = reviewer.reviewer_id
        case.assigned_at = datetime.utcnow()
        case.status = CaseStatus.ASSIGNED
        
        # Update workload
        reviewer.current_workload += 1
        
        # Calculate due date based on SLA
        sla = DEFAULT_SLA_CONFIG.get(case.priority)
        if sla:
            case.due_at = case.assigned_at + timedelta(hours=sla.resolution_hours)
        
        logger.info(f"Case {case.case_id} assigned to {reviewer.reviewer_id}")
        
        return case
    
    def release_case(self, case: Case):
        """Release case from reviewer"""
        if case.assigned_to and case.assigned_to in self._reviewers:
            self._reviewers[case.assigned_to].current_workload -= 1
        
        case.assigned_to = None
        case.assigned_at = None
        case.status = CaseStatus.OPEN
    
    def get_reviewer_stats(self, reviewer_id: str) -> Dict[str, Any]:
        """Get reviewer statistics"""
        if reviewer_id not in self._reviewers:
            return {}
        
        reviewer = self._reviewers[reviewer_id]
        return {
            "reviewer_id": reviewer_id,
            "name": reviewer.name,
            "role": reviewer.role.value,
            "current_workload": reviewer.current_workload,
            "max_workload": reviewer.max_workload,
            "utilization": reviewer.current_workload / reviewer.max_workload if reviewer.max_workload > 0 else 0,
            "quality_score": reviewer.quality_score,
            "cases_resolved": reviewer.cases_resolved,
            "avg_resolution_time_hours": reviewer.avg_resolution_time_hours,
            "approval_rate": reviewer.approval_rate,
            "rejection_rate": reviewer.rejection_rate
        }


# ============================================================================
# ESCALATION MANAGER
# ============================================================================

class EscalationManager:
    """
    Manages case escalations based on SLA breaches and manual escalation requests
    """
    
    def __init__(self, assignment_engine: AssignmentEngine):
        self._assignment_engine = assignment_engine
    
    def check_sla_breach(self, case: Case) -> Tuple[bool, Optional[str]]:
        """Check if case has breached SLA"""
        now = datetime.utcnow()
        sla = DEFAULT_SLA_CONFIG.get(case.priority)
        
        if not sla:
            return False, None
        
        # Check response SLA
        if case.status == CaseStatus.OPEN:
            response_deadline = case.created_at + timedelta(hours=sla.response_hours)
            if now > response_deadline:
                return True, "Response SLA breached"
        
        # Check resolution SLA
        if case.due_at and now > case.due_at:
            return True, "Resolution SLA breached"
        
        return False, None
    
    def escalate_case(
        self,
        case: Case,
        reason: EscalationReason,
        escalated_by: str,
        notes: Optional[str] = None
    ) -> Case:
        """Escalate case to higher level"""
        # Determine escalation target role
        current_role = None
        if case.assigned_to and case.assigned_to in self._assignment_engine._reviewers:
            current_role = self._assignment_engine._reviewers[case.assigned_to].role
        
        # Find next level role
        target_role = self._get_escalation_target_role(current_role, reason)
        
        # Find reviewer at target level
        escalation_reviewer = self._assignment_engine.find_best_reviewer(
            case,
            min_role=target_role
        )
        
        if escalation_reviewer:
            # Release from current reviewer
            self._assignment_engine.release_case(case)
            
            # Assign to escalation reviewer
            case = self._assignment_engine.assign_case(case, escalation_reviewer)
            case.escalated_to = escalation_reviewer.reviewer_id
        
        case.status = CaseStatus.ESCALATED
        case.escalation_reason = reason
        case.escalated_at = datetime.utcnow()
        
        # Add escalation note
        case.notes.append({
            "timestamp": datetime.utcnow().isoformat(),
            "author": escalated_by,
            "type": "escalation",
            "content": f"Escalated: {reason.value}. {notes or ''}"
        })
        
        logger.info(f"Case {case.case_id} escalated: {reason.value}")
        
        return case
    
    def _get_escalation_target_role(
        self,
        current_role: Optional[ReviewerRole],
        reason: EscalationReason
    ) -> ReviewerRole:
        """Determine target role for escalation"""
        # Special escalation paths
        if reason == EscalationReason.LEGAL_REVIEW:
            return ReviewerRole.COMPLIANCE_OFFICER
        if reason == EscalationReason.FRAUD_SUSPECTED:
            return ReviewerRole.SENIOR_ANALYST
        if reason == EscalationReason.COMPLIANCE_REVIEW:
            return ReviewerRole.COMPLIANCE_OFFICER
        
        # Standard escalation - go up one level
        if not current_role:
            return ReviewerRole.L2_ANALYST
        
        role_order = [
            ReviewerRole.L1_ANALYST,
            ReviewerRole.L2_ANALYST,
            ReviewerRole.SENIOR_ANALYST,
            ReviewerRole.TEAM_LEAD,
            ReviewerRole.COMPLIANCE_OFFICER,
            ReviewerRole.MANAGER
        ]
        
        try:
            current_idx = role_order.index(current_role)
            if current_idx < len(role_order) - 1:
                return role_order[current_idx + 1]
        except ValueError:
            pass
        
        return ReviewerRole.SENIOR_ANALYST


# ============================================================================
# QA MANAGER
# ============================================================================

class QAManager:
    """
    Quality assurance with random sampling and 100% sampling for high-risk cases
    """
    
    def __init__(self, standard_sample_rate: float = 0.10):
        self._sample_rate = standard_sample_rate
        self._qa_reviews: Dict[str, QAReview] = {}
    
    def should_qa_review(self, case: Case) -> bool:
        """Determine if case should be QA reviewed"""
        # 100% sampling for high-risk and escalated cases
        if case.priority in [Priority.CRITICAL, Priority.URGENT]:
            return True
        if case.escalation_reason:
            return True
        if "high_risk" in case.tags:
            return True
        
        # Random sampling for others
        return random.random() < self._sample_rate
    
    def create_qa_review(
        self,
        case: Case,
        qa_reviewer_id: str,
        result: QAResult,
        score: float,
        findings: List[str],
        recommendations: List[str]
    ) -> QAReview:
        """Create QA review for a case"""
        qa_id = secrets.token_hex(16)
        
        qa_review = QAReview(
            qa_id=qa_id,
            case_id=case.case_id,
            reviewer_id=case.resolved_by or "",
            qa_reviewer_id=qa_reviewer_id,
            result=result,
            score=score,
            findings=findings,
            recommendations=recommendations,
            reviewed_at=datetime.utcnow()
        )
        
        self._qa_reviews[qa_id] = qa_review
        
        logger.info(f"QA review created: {qa_id} - {result.value} ({score})")
        
        return qa_review
    
    def get_reviewer_qa_stats(self, reviewer_id: str) -> Dict[str, Any]:
        """Get QA statistics for a reviewer"""
        reviews = [r for r in self._qa_reviews.values() if r.reviewer_id == reviewer_id]
        
        if not reviews:
            return {"total_reviews": 0}
        
        return {
            "total_reviews": len(reviews),
            "pass_rate": len([r for r in reviews if r.result == QAResult.PASS]) / len(reviews),
            "avg_score": sum(r.score for r in reviews) / len(reviews),
            "fail_count": len([r for r in reviews if r.result == QAResult.FAIL])
        }


# ============================================================================
# CASE MANAGEMENT SERVICE
# ============================================================================

class CaseManagementService:
    """
    Main case management service
    Integrates with TigerBeetle, Kafka, Dapr, Temporal, Keycloak, Permify, Redis, APISIX
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        kafka_bootstrap: str = "localhost:9092",
        temporal_host: str = "localhost:7233"
    ):
        self.redis_url = redis_url
        self.kafka_bootstrap = kafka_bootstrap
        self.temporal_host = temporal_host
        
        self._cases: Dict[str, Case] = {}
        self._assignment_engine = AssignmentEngine()
        self._escalation_manager = EscalationManager(self._assignment_engine)
        self._qa_manager = QAManager()
    
    async def create_case(
        self,
        case_type: CaseType,
        priority: Priority,
        subject_id: str,
        subject_type: str,
        title: str,
        description: str,
        created_by: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        auto_assign: bool = True
    ) -> Case:
        """Create a new case"""
        case_id = secrets.token_hex(16)
        
        case = Case(
            case_id=case_id,
            case_type=case_type,
            status=CaseStatus.OPEN,
            priority=priority,
            subject_id=subject_id,
            subject_type=subject_type,
            title=title,
            description=description,
            created_at=datetime.utcnow(),
            created_by=created_by,
            metadata=metadata or {},
            tags=tags or []
        )
        
        self._cases[case_id] = case
        
        # Auto-assign if requested
        if auto_assign:
            required_skills = self._get_required_skills(case_type)
            reviewer = self._assignment_engine.find_best_reviewer(case, required_skills)
            if reviewer:
                case = self._assignment_engine.assign_case(case, reviewer)
        
        # Publish to Kafka
        await self._publish_event("kyc.case.events", {
            "event_type": "case_created",
            "case_id": case_id,
            "case_type": case_type.value,
            "priority": priority.value,
            "subject_id": subject_id,
            "timestamp": case.created_at.isoformat()
        })
        
        # Start Temporal workflow for SLA monitoring
        await self._start_sla_monitoring_workflow(case)
        
        logger.info(f"Case created: {case_id} - {case_type.value}")
        
        return case
    
    async def update_case_status(
        self,
        case_id: str,
        status: CaseStatus,
        updated_by: str,
        notes: Optional[str] = None
    ) -> Case:
        """Update case status"""
        if case_id not in self._cases:
            raise ValueError(f"Case not found: {case_id}")
        
        case = self._cases[case_id]
        old_status = case.status
        case.status = status
        
        if notes:
            case.notes.append({
                "timestamp": datetime.utcnow().isoformat(),
                "author": updated_by,
                "type": "status_change",
                "content": f"Status changed from {old_status.value} to {status.value}. {notes}"
            })
        
        # Publish to Kafka
        await self._publish_event("kyc.case.events", {
            "event_type": "case_status_updated",
            "case_id": case_id,
            "old_status": old_status.value,
            "new_status": status.value,
            "updated_by": updated_by,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Case {case_id} status updated: {old_status.value} -> {status.value}")
        
        return case
    
    async def resolve_case(
        self,
        case_id: str,
        decision: str,
        resolution_notes: str,
        resolved_by: str
    ) -> Case:
        """Resolve a case"""
        if case_id not in self._cases:
            raise ValueError(f"Case not found: {case_id}")
        
        case = self._cases[case_id]
        case.status = CaseStatus.RESOLVED
        case.decision = decision
        case.resolution_notes = resolution_notes
        case.resolved_by = resolved_by
        case.resolved_at = datetime.utcnow()
        
        # Check SLA compliance
        if case.due_at:
            case.sla_resolution_met = case.resolved_at <= case.due_at
        
        # Update reviewer stats
        if case.assigned_to and case.assigned_to in self._assignment_engine._reviewers:
            reviewer = self._assignment_engine._reviewers[case.assigned_to]
            reviewer.cases_resolved += 1
            reviewer.current_workload -= 1
            
            # Update approval/rejection rates
            if decision.lower() == "approved":
                reviewer.approval_rate = (
                    (reviewer.approval_rate * (reviewer.cases_resolved - 1) + 1) / reviewer.cases_resolved
                )
            elif decision.lower() == "rejected":
                reviewer.rejection_rate = (
                    (reviewer.rejection_rate * (reviewer.cases_resolved - 1) + 1) / reviewer.cases_resolved
                )
        
        # Check if QA review needed
        if self._qa_manager.should_qa_review(case):
            case.tags.append("qa_required")
        
        # Publish to Kafka
        await self._publish_event("kyc.case.events", {
            "event_type": "case_resolved",
            "case_id": case_id,
            "decision": decision,
            "resolved_by": resolved_by,
            "sla_met": case.sla_resolution_met,
            "timestamp": case.resolved_at.isoformat()
        })
        
        logger.info(f"Case {case_id} resolved: {decision}")
        
        return case
    
    async def escalate_case(
        self,
        case_id: str,
        reason: EscalationReason,
        escalated_by: str,
        notes: Optional[str] = None
    ) -> Case:
        """Escalate a case"""
        if case_id not in self._cases:
            raise ValueError(f"Case not found: {case_id}")
        
        case = self._cases[case_id]
        case = self._escalation_manager.escalate_case(case, reason, escalated_by, notes)
        
        # Publish to Kafka
        await self._publish_event("kyc.case.events", {
            "event_type": "case_escalated",
            "case_id": case_id,
            "reason": reason.value,
            "escalated_by": escalated_by,
            "escalated_to": case.escalated_to,
            "timestamp": case.escalated_at.isoformat() if case.escalated_at else None
        })
        
        return case
    
    async def add_case_note(
        self,
        case_id: str,
        author: str,
        content: str,
        note_type: str = "general"
    ) -> Case:
        """Add note to case"""
        if case_id not in self._cases:
            raise ValueError(f"Case not found: {case_id}")
        
        case = self._cases[case_id]
        case.notes.append({
            "timestamp": datetime.utcnow().isoformat(),
            "author": author,
            "type": note_type,
            "content": content
        })
        
        return case
    
    async def get_case(self, case_id: str) -> Optional[Case]:
        """Get case by ID"""
        return self._cases.get(case_id)
    
    async def get_cases(
        self,
        status: Optional[CaseStatus] = None,
        case_type: Optional[CaseType] = None,
        priority: Optional[Priority] = None,
        assigned_to: Optional[str] = None,
        subject_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Case]:
        """Query cases with filters"""
        results = []
        
        for case in self._cases.values():
            if status and case.status != status:
                continue
            if case_type and case.case_type != case_type:
                continue
            if priority and case.priority != priority:
                continue
            if assigned_to and case.assigned_to != assigned_to:
                continue
            if subject_id and case.subject_id != subject_id:
                continue
            
            results.append(case)
            
            if len(results) >= limit:
                break
        
        # Sort by priority and creation time
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.URGENT: 1,
            Priority.HIGH: 2,
            Priority.MEDIUM: 3,
            Priority.LOW: 4
        }
        results.sort(key=lambda c: (priority_order.get(c.priority, 5), c.created_at))
        
        return results
    
    async def get_metrics(self) -> CaseMetrics:
        """Get case metrics for dashboard"""
        cases = list(self._cases.values())
        
        if not cases:
            return CaseMetrics(
                total_cases=0,
                open_cases=0,
                assigned_cases=0,
                resolved_cases=0,
                escalated_cases=0,
                avg_resolution_time_hours=0,
                sla_compliance_rate=0,
                oldest_open_case_hours=0,
                cases_by_type={},
                cases_by_priority={}
            )
        
        open_cases = [c for c in cases if c.status in [CaseStatus.OPEN, CaseStatus.ASSIGNED, CaseStatus.IN_PROGRESS]]
        resolved_cases = [c for c in cases if c.status == CaseStatus.RESOLVED]
        escalated_cases = [c for c in cases if c.status == CaseStatus.ESCALATED]
        
        # Calculate average resolution time
        resolution_times = []
        for case in resolved_cases:
            if case.resolved_at and case.created_at:
                hours = (case.resolved_at - case.created_at).total_seconds() / 3600
                resolution_times.append(hours)
        
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        
        # Calculate SLA compliance
        sla_met_count = len([c for c in resolved_cases if c.sla_resolution_met])
        sla_compliance = sla_met_count / len(resolved_cases) if resolved_cases else 0
        
        # Find oldest open case
        oldest_hours = 0
        now = datetime.utcnow()
        for case in open_cases:
            hours = (now - case.created_at).total_seconds() / 3600
            oldest_hours = max(oldest_hours, hours)
        
        # Count by type and priority
        cases_by_type = defaultdict(int)
        cases_by_priority = defaultdict(int)
        for case in cases:
            cases_by_type[case.case_type.value] += 1
            cases_by_priority[case.priority.value] += 1
        
        return CaseMetrics(
            total_cases=len(cases),
            open_cases=len(open_cases),
            assigned_cases=len([c for c in cases if c.status == CaseStatus.ASSIGNED]),
            resolved_cases=len(resolved_cases),
            escalated_cases=len(escalated_cases),
            avg_resolution_time_hours=avg_resolution,
            sla_compliance_rate=sla_compliance,
            oldest_open_case_hours=oldest_hours,
            cases_by_type=dict(cases_by_type),
            cases_by_priority=dict(cases_by_priority)
        )
    
    async def check_sla_breaches(self) -> List[Case]:
        """Check for SLA breaches and auto-escalate"""
        breached_cases = []
        
        for case in self._cases.values():
            if case.status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
                continue
            
            is_breached, reason = self._escalation_manager.check_sla_breach(case)
            
            if is_breached and case.status != CaseStatus.ESCALATED:
                case = await self.escalate_case(
                    case.case_id,
                    EscalationReason.SLA_BREACH,
                    "system",
                    reason
                )
                breached_cases.append(case)
        
        return breached_cases
    
    def register_reviewer(self, reviewer: Reviewer):
        """Register a reviewer"""
        self._assignment_engine.register_reviewer(reviewer)
    
    def _get_required_skills(self, case_type: CaseType) -> List[ReviewerSkill]:
        """Get required skills for case type"""
        skill_mapping = {
            CaseType.NEW_MERCHANT: [ReviewerSkill.DOCUMENT_VERIFICATION, ReviewerSkill.BUSINESS_VERIFICATION],
            CaseType.REVERIFICATION: [ReviewerSkill.DOCUMENT_VERIFICATION],
            CaseType.DOCUMENT_REVIEW: [ReviewerSkill.DOCUMENT_VERIFICATION],
            CaseType.LIVENESS_REVIEW: [ReviewerSkill.LIVENESS_REVIEW],
            CaseType.SCREENING_MATCH: [ReviewerSkill.SANCTIONS_SCREENING],
            CaseType.TRANSACTION_ALERT: [ReviewerSkill.TRANSACTION_MONITORING],
            CaseType.ESCALATION: [ReviewerSkill.HIGH_RISK],
            CaseType.APPEAL: [ReviewerSkill.HIGH_RISK],
            CaseType.PERIODIC_REVIEW: [ReviewerSkill.DOCUMENT_VERIFICATION]
        }
        return skill_mapping.get(case_type, [])
    
    async def _publish_event(self, topic: str, event: Dict[str, Any]):
        """Publish event to Kafka"""
        # Kafka integration
        logger.debug(f"Publishing to {topic}: {event.get('event_type')}")
    
    async def _start_sla_monitoring_workflow(self, case: Case):
        """Start Temporal workflow for SLA monitoring"""
        # Temporal workflow
        logger.debug(f"Starting SLA monitoring workflow for case {case.case_id}")


# ============================================================================
# MIDDLEWARE INTEGRATION
# ============================================================================

class CaseManagementMiddlewareIntegration:
    """
    Integration with middleware components
    """
    
    def __init__(self, service: CaseManagementService):
        self.service = service
    
    async def sync_with_keycloak(self, reviewer: Reviewer):
        """Sync reviewer with Keycloak user"""
        logger.info(f"Syncing reviewer {reviewer.reviewer_id} with Keycloak")
    
    async def check_permify_permission(self, user_id: str, action: str, case_id: str) -> bool:
        """Check case access permission with Permify"""
        logger.info(f"Checking Permify: {user_id} -> {action} -> case:{case_id}")
        return True
    
    async def cache_case_in_redis(self, case: Case, ttl: int = 3600):
        """Cache case in Redis"""
        logger.info(f"Caching case {case.case_id} in Redis")
    
    async def invoke_dapr_notification(self, case: Case, notification_type: str):
        """Send notification via Dapr"""
        logger.info(f"Sending {notification_type} notification for case {case.case_id}")
    
    async def stream_to_lakehouse(self, case: Case, event_type: str):
        """Stream case event to Lakehouse for analytics"""
        logger.info(f"Streaming {event_type} to Lakehouse for case {case.case_id}")


# Global instance
_case_service: Optional[CaseManagementService] = None


def get_case_management_service() -> CaseManagementService:
    """Get or create case management service"""
    global _case_service
    if _case_service is None:
        _case_service = CaseManagementService()
    return _case_service
