# Enhanced Agent Onboarding Service with Validators and Additional Endpoints
# This file extends the original agent_onboarding_service.py with:
# 1. Pydantic validators for data quality
# 2. Additional API endpoints for complete functionality

from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, func, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr, validator, constr, confloat, conint
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import hashlib
import hmac
import jwt
import aiofiles
import asyncio
import httpx
import os
import json
import re
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI app
app = FastAPI(
    title="Enhanced Agent Onboarding Service",
    description="Comprehensive agent onboarding with KYC/KYB workflows, validators, and complete API",
    version="2.0.0"
)

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
if _ALLOWED_ORIGINS == [""]:
    _ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Enums
class OnboardingStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ADDITIONAL_INFO_REQUIRED = "additional_info_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    SUSPENDED = "suspended"

class DocumentType(str, Enum):
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    BUSINESS_LICENSE = "business_license"
    TAX_CERTIFICATE = "tax_certificate"
    BANK_STATEMENT = "bank_statement"
    PROOF_OF_ADDRESS = "proof_of_address"
    REFERENCE_LETTER = "reference_letter"
    PHOTO = "photo"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"

class AgentTier(str, Enum):
    SUPER_AGENT = "Super Agent"
    REGIONAL_AGENT = "Regional Agent"
    FIELD_AGENT = "Field Agent"
    SUB_AGENT = "Sub Agent"

# Enhanced Pydantic Models with Validators
class AgentOnboardingCreate(BaseModel):
    # Personal Information
    first_name: constr(min_length=2, max_length=50)
    last_name: constr(min_length=2, max_length=50)
    email: EmailStr
    phone: str
    date_of_birth: Optional[datetime] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    
    # Address Information
    street_address: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    # Business Information
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    business_registration_number: Optional[str] = None
    tax_identification_number: Optional[str] = None
    years_in_business: Optional[conint(ge=0, le=100)] = None
    
    # Agent Information
    requested_tier: AgentTier
    territory_preference: Optional[str] = None
    expected_monthly_volume: Optional[confloat(ge=0)] = None
    banking_experience_years: Optional[conint(ge=0, le=50)] = None
    
    # Referral Information
    referrer_agent_id: Optional[str] = None
    referral_code: Optional[str] = None
    
    # Validators
    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format (E.164)"""
        if not re.match(r'^\+?[1-9]\d{1,14}$', v):
            raise ValueError('Invalid phone number format. Use E.164 format (e.g., +2348012345678)')
        return v
    
    @validator('date_of_birth')
    def validate_age(cls, v):
        """Validate agent is at least 18 years old"""
        if v:
            age = (datetime.now() - v).days / 365.25
            if age < 18:
                raise ValueError('Agent must be at least 18 years old')
            if age > 100:
                raise ValueError('Invalid date of birth')
        return v
    
    @validator('business_registration_number')
    def validate_business_registration(cls, v):
        """Validate business registration number format"""
        if v and len(v) < 5:
            raise ValueError('Business registration number must be at least 5 characters')
        return v
    
    @validator('tax_identification_number')
    def validate_tax_id(cls, v):
        """Validate tax identification number format"""
        if v and len(v) < 8:
            raise ValueError('Tax identification number must be at least 8 characters')
        return v
    
    @validator('email')
    def validate_email_domain(cls, v):
        """Additional email validation"""
        # Block disposable email domains
        disposable_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com']
        domain = v.split('@')[1].lower()
        if domain in disposable_domains:
            raise ValueError('Disposable email addresses are not allowed')
        return v.lower()
    
    @validator('expected_monthly_volume')
    def validate_volume(cls, v, values):
        """Validate expected monthly volume based on tier"""
        if v and 'requested_tier' in values:
            tier = values['requested_tier']
            if tier == AgentTier.SUB_AGENT and v > 100000:
                raise ValueError('Sub Agent expected volume should not exceed 100,000')
            elif tier == AgentTier.FIELD_AGENT and v > 500000:
                raise ValueError('Field Agent expected volume should not exceed 500,000')
        return v

class ApprovalRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    comments: Optional[str] = None
    conditions: Optional[List[str]] = None

class RejectionRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    reason: str
    detailed_reasons: Optional[List[str]] = None

class SuspensionRequest(BaseModel):
    admin_id: str
    admin_name: str
    reason: str
    suspension_duration_days: Optional[int] = None

class ReactivationRequest(BaseModel):
    admin_id: str
    admin_name: str
    notes: Optional[str] = None

class AssignReviewerRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    reviewer_email: str
    priority: Optional[str] = "normal"  # low, normal, high, urgent

class SearchFilters(BaseModel):
    status: Optional[OnboardingStatus] = None
    tier: Optional[AgentTier] = None
    kyc_status: Optional[VerificationStatus] = None
    kyb_status: Optional[VerificationStatus] = None
    min_risk_score: Optional[float] = None
    max_risk_score: Optional[float] = None
    submitted_after: Optional[datetime] = None
    submitted_before: Optional[datetime] = None
    search_query: Optional[str] = None

class StatisticsResponse(BaseModel):
    total_applications: int
    by_status: Dict[str, int]
    by_tier: Dict[str, int]
    by_kyc_status: Dict[str, int]
    by_kyb_status: Dict[str, int]
    avg_risk_score: float
    avg_processing_time_hours: float
    approval_rate: float
    rejection_rate: float

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# ADDITIONAL API ENDPOINTS (10 new endpoints)
# ============================================================================

from agent_onboarding_service import AgentOnboarding, OnboardingDocument, VerificationRecord, ReviewRecord

@app.get("/applications/{id}/documents", tags=["Documents"])
async def list_application_documents(
    id: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """List all documents for an application"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        documents = db.query(OnboardingDocument).filter(OnboardingDocument.application_id == id).all()
        return {
            "application_id": id,
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "document_name": doc.document_name,
                    "file_size": doc.file_size,
                    "mime_type": doc.mime_type,
                    "processing_status": doc.processing_status,
                    "verification_status": doc.verification_status,
                    "verification_score": doc.verification_score,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                }
                for doc in documents
            ],
            "total_count": len(documents),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/{id}/verifications", tags=["Verifications"])
async def list_application_verifications(
    id: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get verification history for an application"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        verifications = db.query(VerificationRecord).filter(VerificationRecord.application_id == id).all()
        return {
            "application_id": id,
            "verifications": [
                {
                    "id": v.id,
                    "verification_type": v.verification_type,
                    "verification_method": v.verification_method,
                    "status": v.status,
                    "score": v.score,
                    "confidence": v.confidence,
                    "external_provider": v.external_provider,
                    "external_reference_id": v.external_reference_id,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "completed_at": v.completed_at.isoformat() if v.completed_at else None,
                }
                for v in verifications
            ],
            "total_count": len(verifications),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing verifications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/{id}/reviews", tags=["Reviews"])
async def list_application_reviews(
    id: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get review history for an application"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        reviews = db.query(ReviewRecord).filter(ReviewRecord.application_id == id).all()
        return {
            "application_id": id,
            "reviews": [
                {
                    "id": r.id,
                    "reviewer_id": r.reviewer_id,
                    "reviewer_name": r.reviewer_name,
                    "review_type": r.review_type,
                    "decision": r.decision,
                    "comments": r.comments,
                    "risk_assessment": r.risk_assessment,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reviews
            ],
            "total_count": len(reviews),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing reviews: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{id}/approve", tags=["Workflow"])
async def approve_application(
    id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Approve an agent application"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        if application.status not in [OnboardingStatus.UNDER_REVIEW, OnboardingStatus.SUBMITTED]:
            raise HTTPException(status_code=400, detail="Application cannot be approved in current status")

        application.status = OnboardingStatus.APPROVED
        application.approved_at = datetime.utcnow()
        application.updated_at = datetime.utcnow()

        review = ReviewRecord(
            application_id=id,
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
            review_type="final",
            decision="approve",
            comments=request.comments,
        )
        db.add(review)
        db.commit()

        logger.info(f"Application {id} approved by {request.reviewer_name}")
        return {
            "application_id": id,
            "status": "approved",
            "approved_at": application.approved_at.isoformat(),
            "approved_by": request.reviewer_name,
            "message": "Application approved successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{id}/reject", tags=["Workflow"])
async def reject_application(
    id: str,
    request: RejectionRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Reject an agent application"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        if application.status not in [OnboardingStatus.UNDER_REVIEW, OnboardingStatus.SUBMITTED]:
            raise HTTPException(status_code=400, detail="Application cannot be rejected in current status")

        application.status = OnboardingStatus.REJECTED
        application.rejected_at = datetime.utcnow()
        application.rejection_reason = request.reason
        application.updated_at = datetime.utcnow()

        review = ReviewRecord(
            application_id=id,
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
            review_type="final",
            decision="reject",
            comments=request.reason,
        )
        db.add(review)
        db.commit()

        logger.info(f"Application {id} rejected by {request.reviewer_name}")
        return {
            "application_id": id,
            "status": "rejected",
            "rejected_at": application.rejected_at.isoformat(),
            "rejected_by": request.reviewer_name,
            "reason": request.reason,
            "message": "Application rejected",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{id}/suspend", tags=["Agent Management"])
async def suspend_agent(
    id: str,
    request: SuspensionRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Suspend an active agent"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        if application.status != OnboardingStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Only active agents can be suspended")

        application.status = OnboardingStatus.SUSPENDED
        application.updated_at = datetime.utcnow()

        suspension_end = None
        if request.suspension_duration_days:
            suspension_end = datetime.utcnow() + timedelta(days=request.suspension_duration_days)

        review = ReviewRecord(
            application_id=id,
            reviewer_id=request.admin_id,
            reviewer_name=request.admin_name,
            review_type="suspension",
            decision="suspend",
            comments=request.reason,
            risk_assessment={"suspension_end": suspension_end.isoformat() if suspension_end else None},
        )
        db.add(review)
        db.commit()

        logger.info(f"Agent {id} suspended by {request.admin_name}")
        return {
            "application_id": id,
            "status": "suspended",
            "suspended_at": datetime.utcnow().isoformat(),
            "suspended_by": request.admin_name,
            "reason": request.reason,
            "suspension_end": suspension_end.isoformat() if suspension_end else None,
            "message": "Agent suspended successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error suspending agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{id}/reactivate", tags=["Agent Management"])
async def reactivate_agent(
    id: str,
    request: ReactivationRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Reactivate a suspended agent"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        if application.status != OnboardingStatus.SUSPENDED:
            raise HTTPException(status_code=400, detail="Only suspended agents can be reactivated")

        application.status = OnboardingStatus.ACTIVE
        application.updated_at = datetime.utcnow()

        review = ReviewRecord(
            application_id=id,
            reviewer_id=request.admin_id,
            reviewer_name=request.admin_name,
            review_type="reactivation",
            decision="reactivate",
            comments=request.notes,
        )
        db.add(review)
        db.commit()

        logger.info(f"Agent {id} reactivated by {request.admin_name}")
        return {
            "application_id": id,
            "status": "active",
            "reactivated_at": datetime.utcnow().isoformat(),
            "reactivated_by": request.admin_name,
            "message": "Agent reactivated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error reactivating agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/{id}/assign", tags=["Workflow"])
async def assign_reviewer(
    id: str,
    request: AssignReviewerRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Assign a reviewer to an application"""
    try:
        application = db.query(AgentOnboarding).filter(AgentOnboarding.id == id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        application.updated_by = request.reviewer_id
        application.updated_at = datetime.utcnow()
        if application.status == OnboardingStatus.SUBMITTED:
            application.status = OnboardingStatus.UNDER_REVIEW

        review = ReviewRecord(
            application_id=id,
            reviewer_id=request.reviewer_id,
            reviewer_name=request.reviewer_name,
            review_type="assignment",
            decision="assigned",
            comments=f"Priority: {request.priority}",
        )
        db.add(review)
        db.commit()

        logger.info(f"Reviewer {request.reviewer_name} assigned to application {id}")
        return {
            "application_id": id,
            "reviewer_id": request.reviewer_id,
            "reviewer_name": request.reviewer_name,
            "reviewer_email": request.reviewer_email,
            "priority": request.priority,
            "assigned_at": datetime.utcnow().isoformat(),
            "message": "Reviewer assigned successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning reviewer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/search", tags=["Search"])
async def search_applications(
    filters: SearchFilters,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search applications with filters"""
    try:
        query = db.query(AgentOnboarding)

        if filters.status:
            query = query.filter(AgentOnboarding.status == filters.status.value)
        if filters.tier:
            query = query.filter(AgentOnboarding.requested_tier == filters.tier.value)
        if filters.kyc_status:
            query = query.filter(AgentOnboarding.kyc_status == filters.kyc_status.value)
        if filters.kyb_status:
            query = query.filter(AgentOnboarding.kyb_status == filters.kyb_status.value)
        if filters.min_risk_score is not None:
            query = query.filter(AgentOnboarding.risk_score >= filters.min_risk_score)
        if filters.max_risk_score is not None:
            query = query.filter(AgentOnboarding.risk_score <= filters.max_risk_score)
        if filters.submitted_after:
            query = query.filter(AgentOnboarding.submitted_at >= filters.submitted_after)
        if filters.submitted_before:
            query = query.filter(AgentOnboarding.submitted_at <= filters.submitted_before)
        if filters.search_query:
            term = f"%{filters.search_query}%"
            query = query.filter(
                or_(
                    AgentOnboarding.first_name.ilike(term),
                    AgentOnboarding.last_name.ilike(term),
                    AgentOnboarding.email.ilike(term),
                    AgentOnboarding.application_number.ilike(term),
                    AgentOnboarding.business_name.ilike(term),
                )
            )

        total_count = query.count()
        offset = (page - 1) * page_size
        applications = query.order_by(AgentOnboarding.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            "applications": [
                {
                    "id": app.id,
                    "application_number": app.application_number,
                    "name": f"{app.first_name} {app.last_name}",
                    "email": app.email,
                    "requested_tier": app.requested_tier,
                    "status": app.status,
                    "kyc_status": app.kyc_status,
                    "kyb_status": app.kyb_status,
                    "risk_score": app.risk_score,
                    "risk_level": app.risk_level,
                    "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
                    "created_at": app.created_at.isoformat() if app.created_at else None,
                }
                for app in applications
            ],
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
        }
    except Exception as e:
        logger.error(f"Error searching applications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/statistics", response_model=StatisticsResponse, tags=["Analytics"])
async def get_statistics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get dashboard statistics for applications"""
    try:
        query = db.query(AgentOnboarding)
        if start_date:
            query = query.filter(AgentOnboarding.created_at >= start_date)
        if end_date:
            query = query.filter(AgentOnboarding.created_at <= end_date)

        total = query.count()

        by_status = dict(
            db.query(AgentOnboarding.status, func.count(AgentOnboarding.id))
            .group_by(AgentOnboarding.status)
            .all()
        )
        by_tier = dict(
            db.query(AgentOnboarding.requested_tier, func.count(AgentOnboarding.id))
            .group_by(AgentOnboarding.requested_tier)
            .all()
        )
        by_kyc = dict(
            db.query(AgentOnboarding.kyc_status, func.count(AgentOnboarding.id))
            .group_by(AgentOnboarding.kyc_status)
            .all()
        )
        by_kyb = dict(
            db.query(AgentOnboarding.kyb_status, func.count(AgentOnboarding.id))
            .group_by(AgentOnboarding.kyb_status)
            .all()
        )

        avg_risk = db.query(func.avg(AgentOnboarding.risk_score)).scalar() or 0.0

        approved_count = by_status.get(OnboardingStatus.APPROVED, 0) + by_status.get(OnboardingStatus.ACTIVE, 0)
        rejected_count = by_status.get(OnboardingStatus.REJECTED, 0)
        decided = approved_count + rejected_count

        avg_hours_row = (
            db.query(
                func.avg(
                    func.extract("epoch", AgentOnboarding.approved_at - AgentOnboarding.submitted_at) / 3600
                )
            )
            .filter(AgentOnboarding.approved_at.isnot(None), AgentOnboarding.submitted_at.isnot(None))
            .scalar()
        )

        return StatisticsResponse(
            total_applications=total,
            by_status={str(k): v for k, v in by_status.items()},
            by_tier={str(k): v for k, v in by_tier.items()},
            by_kyc_status={str(k): v for k, v in by_kyc.items()},
            by_kyb_status={str(k): v for k, v in by_kyb.items()},
            avg_risk_score=float(avg_risk),
            avg_processing_time_hours=float(avg_hours_row) if avg_hours_row else 0.0,
            approval_rate=(approved_count / decided * 100) if decided > 0 else 0.0,
            rejection_rate=(rejected_count / decided * 100) if decided > 0 else 0.0,
        )
    except Exception as e:
        logger.error(f"Error fetching statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "enhanced-agent-onboarding",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "validators": True,
            "additional_endpoints": True,
            "total_endpoints": 18
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

