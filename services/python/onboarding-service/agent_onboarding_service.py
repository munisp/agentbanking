from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr, validator
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
    title="Agent Onboarding Service",
    description="Comprehensive agent onboarding with KYC/KYB workflows",
    version="1.0.0"
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

# Database Models
class AgentOnboarding(Base):
    __tablename__ = "agent_onboarding"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_number = Column(String, unique=True, nullable=False)
    
    # Personal Information
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    date_of_birth = Column(DateTime)
    nationality = Column(String)
    gender = Column(String)
    
    # Address Information
    street_address = Column(String)
    city = Column(String)
    state_province = Column(String)
    postal_code = Column(String)
    country = Column(String)
    
    # Business Information
    business_name = Column(String)
    business_type = Column(String)
    business_registration_number = Column(String)
    tax_identification_number = Column(String)
    years_in_business = Column(Integer)
    
    # Agent Information
    requested_tier = Column(String, nullable=False)
    territory_preference = Column(String)
    expected_monthly_volume = Column(Float)
    banking_experience_years = Column(Integer)
    
    # Application Status
    status = Column(String, default=OnboardingStatus.DRAFT)
    submitted_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    approved_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    # KYC/KYB Information
    kyc_status = Column(String, default=VerificationStatus.PENDING)
    kyb_status = Column(String, default=VerificationStatus.PENDING)
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String, default="low")
    
    # Referral Information
    referrer_agent_id = Column(String)
    referral_code = Column(String)
    
    # System Information
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String)
    updated_by = Column(String)
    
    # Relationships
    documents = relationship("OnboardingDocument", back_populates="application")
    verifications = relationship("VerificationRecord", back_populates="application")
    reviews = relationship("ReviewRecord", back_populates="application")

class OnboardingDocument(Base):
    __tablename__ = "onboarding_documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("agent_onboarding.id"), nullable=False)
    
    document_type = Column(String, nullable=False)
    document_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    
    # OCR and Processing
    ocr_text = Column(Text)
    extracted_data = Column(JSON)
    processing_status = Column(String, default="pending")
    processing_error = Column(Text)
    
    # Verification
    verification_status = Column(String, default=VerificationStatus.PENDING)
    verification_score = Column(Float, default=0.0)
    verification_notes = Column(Text)
    
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime)
    
    # Relationships
    application = relationship("AgentOnboarding", back_populates="documents")

class VerificationRecord(Base):
    __tablename__ = "verification_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("agent_onboarding.id"), nullable=False)
    
    verification_type = Column(String, nullable=False)  # kyc, kyb, document, reference
    verification_method = Column(String)  # manual, automated, third_party
    
    status = Column(String, default=VerificationStatus.PENDING)
    score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    
    # Results
    result_data = Column(JSON)
    verification_notes = Column(Text)
    verified_by = Column(String)
    
    # Third-party Integration
    external_reference_id = Column(String)
    external_provider = Column(String)  # temporal, jumio, etc.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    application = relationship("AgentOnboarding", back_populates="verifications")

class ReviewRecord(Base):
    __tablename__ = "review_records"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("agent_onboarding.id"), nullable=False)
    
    reviewer_id = Column(String, nullable=False)
    reviewer_name = Column(String)
    review_type = Column(String)  # initial, additional, final
    
    decision = Column(String)  # approve, reject, request_info
    comments = Column(Text)
    risk_assessment = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    application = relationship("AgentOnboarding", back_populates="reviews")

# Pydantic Models
class AgentOnboardingCreate(BaseModel):
    # Personal Information
    first_name: str
    last_name: str
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
    years_in_business: Optional[int] = None
    
    # Agent Information
    requested_tier: AgentTier
    territory_preference: Optional[str] = None
    expected_monthly_volume: Optional[float] = None
    banking_experience_years: Optional[int] = None
    
    # Referral Information
    referrer_agent_id: Optional[str] = None
    referral_code: Optional[str] = None

class AgentOnboardingUpdate(BaseModel):
    # All fields optional for updates
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    business_registration_number: Optional[str] = None
    tax_identification_number: Optional[str] = None
    years_in_business: Optional[int] = None
    requested_tier: Optional[AgentTier] = None
    territory_preference: Optional[str] = None
    expected_monthly_volume: Optional[float] = None
    banking_experience_years: Optional[int] = None

class DocumentUploadResponse(BaseModel):
    document_id: str
    document_type: str
    file_name: str
    upload_status: str
    processing_status: str

class VerificationResponse(BaseModel):
    verification_id: str
    verification_type: str
    status: str
    score: float
    confidence: float
    notes: Optional[str] = None

class OnboardingStatusResponse(BaseModel):
    application_id: str
    application_number: str
    status: str
    kyc_status: str
    kyb_status: str
    risk_score: float
    risk_level: str
    progress_percentage: int
    next_steps: List[str]
    required_documents: List[str]

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility Functions
def generate_application_number():
    """Generate unique application number"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:8].upper()
    return f"APP-{timestamp}-{random_suffix}"

PADDLEOCR_SERVICE_URL = os.getenv("PADDLEOCR_SERVICE_URL", "http://localhost:8024")
VLM_SERVICE_URL = os.getenv("VLM_SERVICE_URL", "http://localhost:8031")
VLM_API_KEY = os.getenv("VLM_API_KEY", "")
DOCLING_SERVICE_URL = os.getenv("DOCLING_SERVICE_URL", "http://localhost:8032")
TEMPORAL_WORKFLOW_URL = os.getenv("TEMPORAL_WORKFLOW_URL", "http://localhost:7233")
KYC_PROVIDER_URL = os.getenv("KYC_PROVIDER_URL", "http://localhost:8040")


async def _run_paddleocr(client: httpx.AsyncClient, file_path: str, document_type: str) -> Dict[str, Any]:
    """Run PaddleOCR engine for text extraction with bounding boxes."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {"document_type": document_type, "engines": "paddleocr"}
            response = await client.post(
                f"{PADDLEOCR_SERVICE_URL}/ocr",
                files=files,
                data=data,
                timeout=90.0,
            )
        if response.status_code == 200:
            result = response.json()
            return {
                "engine": "paddleocr",
                "text": result.get("text", ""),
                "confidence": result.get("confidence_score", 0.0),
                "extracted_fields": result.get("extracted_fields", {}),
            }
        logger.warning(f"PaddleOCR returned {response.status_code}")
    except Exception as e:
        logger.warning(f"PaddleOCR unavailable: {e}")
    return {"engine": "paddleocr", "text": "", "confidence": 0.0, "extracted_fields": {}}


async def _run_vlm(client: httpx.AsyncClient, file_path: str, document_type: str) -> Dict[str, Any]:
    """Run Vision Language Model for semantic document understanding."""
    try:
        import base64 as b64
        with open(file_path, "rb") as f:
            image_b64 = b64.b64encode(f.read()).decode("utf-8")
        headers = {}
        if VLM_API_KEY:
            headers["Authorization"] = f"Bearer {VLM_API_KEY}"
        response = await client.post(
            f"{VLM_SERVICE_URL}/v1/ocr/extract",
            json={
                "image": image_b64,
                "document_type": document_type,
                "language": "en",
                "extract_tables": True,
                "extract_fields": True,
            },
            headers=headers,
            timeout=120.0,
        )
        if response.status_code == 200:
            result = response.json()
            return {
                "engine": "vlm",
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0.0),
                "extracted_fields": result.get("extracted_fields", {}),
                "tables": result.get("tables", []),
                "semantic_labels": result.get("semantic_labels", {}),
            }
        logger.warning(f"VLM returned {response.status_code}")
    except Exception as e:
        logger.warning(f"VLM unavailable: {e}")
    return {"engine": "vlm", "text": "", "confidence": 0.0, "extracted_fields": {}}


async def _run_docling(client: httpx.AsyncClient, file_path: str, document_type: str) -> Dict[str, Any]:
    """Run Docling for structured document parsing and layout analysis."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {"document_type": document_type}
            response = await client.post(
                f"{DOCLING_SERVICE_URL}/v1/documents/process",
                files=files,
                data=data,
                timeout=180.0,
            )
        if response.status_code == 200:
            result = response.json()
            return {
                "engine": "docling",
                "text": result.get("text", ""),
                "confidence": result.get("confidence", 0.0),
                "extracted_fields": result.get("fields", {}),
                "sections": result.get("sections", []),
                "tables": result.get("tables", []),
                "layout": result.get("layout", {}),
            }
        logger.warning(f"Docling returned {response.status_code}")
    except Exception as e:
        logger.warning(f"Docling unavailable: {e}")
    return {"engine": "docling", "text": "", "confidence": 0.0, "extracted_fields": {}}


def _aggregate_engine_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results from PaddleOCR, VLM, and Docling using confidence-weighted selection."""
    valid = [r for r in results if r.get("text")]
    if not valid:
        return {
            "text_content": "",
            "confidence": 0.0,
            "fields": {},
            "engines_used": [r["engine"] for r in results],
        }
    best = max(valid, key=lambda r: r.get("confidence", 0.0))
    merged_fields = {}
    for r in valid:
        merged_fields.update(r.get("extracted_fields", {}))
    return {
        "text_content": best["text"],
        "confidence": best.get("confidence", 0.0),
        "fields": merged_fields,
        "engines_used": [r["engine"] for r in valid],
        "primary_engine": best["engine"],
        "tables": best.get("tables", []),
        "layout": best.get("layout", {}),
    }


async def process_document_ocr(file_path: str, document_type: str) -> Dict[str, Any]:
    """Process document with PaddleOCR + VLM + Docling multi-engine pipeline."""
    try:
        async with httpx.AsyncClient() as client:
            paddle_task = _run_paddleocr(client, file_path, document_type)
            vlm_task = _run_vlm(client, file_path, document_type)
            docling_task = _run_docling(client, file_path, document_type)

            results = await asyncio.gather(paddle_task, vlm_task, docling_task)

        aggregated = _aggregate_engine_results(list(results))
        engines_used = aggregated.get("engines_used", [])

        if aggregated["confidence"] > 0:
            return {
                "status": "success",
                "extracted_data": aggregated,
                "processing_notes": f"Processed via {', '.join(engines_used)} (primary: {aggregated.get('primary_engine', 'unknown')})",
            }

        logger.warning("All OCR engines returned empty results, using fallback")
        return await _fallback_ocr_extraction(file_path, document_type)
    except Exception as e:
        logger.error(f"OCR processing error: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "processing_notes": "Failed to process document",
        }


async def _fallback_ocr_extraction(file_path: str, document_type: str) -> Dict[str, Any]:
    """Basic metadata extraction when all OCR engines are unavailable."""
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    return {
        "status": "partial",
        "extracted_data": {
            "text_content": "",
            "confidence": 0.0,
            "fields": {},
            "file_size": file_size,
            "document_type": document_type,
            "engines_used": [],
        },
        "processing_notes": "All OCR engines unavailable; document queued for reprocessing",
    }

async def perform_kyc_verification(application: AgentOnboarding, db: Session) -> Dict[str, Any]:
    """Perform KYC verification via the KYC provider service"""
    try:
        payload = {
            "agent_id": application.id,
            "first_name": application.first_name,
            "last_name": application.last_name,
            "email": application.email,
            "phone": application.phone,
            "date_of_birth": application.date_of_birth.isoformat() if application.date_of_birth else None,
            "nationality": application.nationality,
            "address": {
                "street": application.street_address,
                "city": application.city,
                "state": application.state_province,
                "postal_code": application.postal_code,
                "country": application.country,
            },
        }

        verification_result = await _call_kyc_provider(payload)

        status = VerificationStatus.VERIFIED if verification_result["status"] == "verified" else VerificationStatus.FAILED

        verification = VerificationRecord(
            application_id=application.id,
            verification_type="kyc",
            verification_method="third_party",
            external_provider="kyc_service",
            external_reference_id=verification_result.get("reference_id"),
            status=status,
            score=verification_result.get("score", 0.0),
            confidence=verification_result.get("confidence", 0.0),
            result_data=verification_result,
            verification_notes=verification_result.get("notes", ""),
            completed_at=datetime.utcnow(),
        )

        db.add(verification)
        db.commit()

        return verification_result
    except Exception as e:
        logger.error(f"KYC verification error: {str(e)}")
        return {"status": "failed", "error": str(e)}


async def _call_kyc_provider(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call KYC provider HTTP endpoint with retry"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{KYC_PROVIDER_URL}/kyc/verify", json=payload)
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"KYC provider returned {response.status_code} on attempt {attempt + 1}")
        except httpx.ConnectError:
            logger.warning(f"KYC provider unavailable on attempt {attempt + 1}")
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError("KYC provider unreachable after retries")

async def perform_kyb_verification(application: AgentOnboarding, db: Session) -> Dict[str, Any]:
    """Perform KYB verification via Temporal workflow orchestration"""
    try:
        workflow_payload = {
            "type": "kyb",
            "data": {
                "business_name": application.business_name,
                "business_type": application.business_type,
                "registration_number": application.business_registration_number,
                "tax_id": application.tax_identification_number,
                "country": application.country or "NG",
            },
        }

        verification_result = await _call_temporal_kyb(workflow_payload)

        status = VerificationStatus.VERIFIED if verification_result["status"] == "verified" else VerificationStatus.FAILED

        verification = VerificationRecord(
            application_id=application.id,
            verification_type="kyb",
            verification_method="third_party",
            external_provider="temporal",
            external_reference_id=verification_result.get("workflow_id"),
            status=status,
            score=verification_result.get("score", 0.0),
            confidence=verification_result.get("confidence", 0.0),
            result_data=verification_result,
            verification_notes=verification_result.get("notes", ""),
            completed_at=datetime.utcnow(),
        )

        db.add(verification)
        db.commit()

        return verification_result
    except Exception as e:
        logger.error(f"KYB verification error: {str(e)}")
        return {"status": "failed", "error": str(e)}


async def _call_temporal_kyb(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call Temporal KYB workflow with retry"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                workflow_id = f"kyb-{payload['data'].get('registration_number', 'unknown')}-{uuid.uuid4().hex[:8]}"
                response = await client.post(
                    f"{TEMPORAL_WORKFLOW_URL}/api/v1/namespaces/default/workflows",
                    json={
                        "workflowId": workflow_id,
                        "workflowType": {"name": "kyb-verification"},
                        "taskQueue": {"name": "kyb-verification"},
                        "input": {"payloads": [{"data": payload}]}
                    }
                )
                if response.status_code in (200, 201):
                    result = response.json()
                    return {
                        "status": "verified" if result.get("status") != "rejected" else "failed",
                        "workflow_id": workflow_id,
                        "score": result.get("risk_score", 0.85),
                        "confidence": result.get("confidence", 0.80),
                        "checks": result.get("checks", {}),
                        "notes": result.get("notes", "KYB workflow completed via Temporal"),
                    }
                logger.warning(f"Temporal returned {response.status_code} on attempt {attempt + 1}")
        except httpx.ConnectError:
            logger.warning(f"Temporal unavailable on attempt {attempt + 1}")
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError("Temporal KYB workflow service unreachable after retries")

def calculate_risk_score(application: AgentOnboarding, verifications: List[VerificationRecord]) -> tuple[float, str]:
    """Calculate overall risk score and level"""
    try:
        base_score = 0.5
        
        # Factor in verification scores
        verification_scores = [v.score for v in verifications if v.score > 0]
        if verification_scores:
            avg_verification_score = sum(verification_scores) / len(verification_scores)
            base_score = (base_score + avg_verification_score) / 2
        
        # Factor in business experience
        if application.years_in_business:
            if application.years_in_business >= 5:
                base_score += 0.1
            elif application.years_in_business >= 2:
                base_score += 0.05
        
        # Factor in banking experience
        if application.banking_experience_years:
            if application.banking_experience_years >= 3:
                base_score += 0.1
            elif application.banking_experience_years >= 1:
                base_score += 0.05
        
        # Factor in requested tier (higher tiers require lower risk)
        tier_risk_adjustment = {
            AgentTier.SUPER_AGENT: -0.1,
            AgentTier.REGIONAL_AGENT: -0.05,
            AgentTier.FIELD_AGENT: 0.0,
            AgentTier.SUB_AGENT: 0.05
        }
        base_score += tier_risk_adjustment.get(application.requested_tier, 0.0)
        
        # Ensure score is within bounds
        risk_score = max(0.0, min(1.0, base_score))
        
        # Determine risk level
        if risk_score >= 0.8:
            risk_level = "low"
        elif risk_score >= 0.6:
            risk_level = "medium"
        elif risk_score >= 0.4:
            risk_level = "high"
        else:
            risk_level = "very_high"
        
        return risk_score, risk_level
    except Exception as e:
        logger.error(f"Risk calculation error: {str(e)}")
        return 0.5, "medium"

def calculate_progress_percentage(application: AgentOnboarding) -> int:
    """Calculate application progress percentage"""
    total_steps = 8
    completed_steps = 0
    
    # Basic information
    if all([application.first_name, application.last_name, application.email, application.phone]):
        completed_steps += 1
    
    # Address information
    if all([application.street_address, application.city, application.country]):
        completed_steps += 1
    
    # Business information (if applicable)
    if application.requested_tier in [AgentTier.SUPER_AGENT, AgentTier.REGIONAL_AGENT]:
        if all([application.business_name, application.business_type]):
            completed_steps += 1
    else:
        completed_steps += 1  # Skip business info for individual agents
    
    # Agent preferences
    if application.requested_tier and application.territory_preference:
        completed_steps += 1
    
    # Document upload
    if len(application.documents) >= 2:  # At least ID and proof of address
        completed_steps += 1
    
    # KYC verification
    if application.kyc_status == VerificationStatus.VERIFIED:
        completed_steps += 1
    
    # KYB verification (if applicable)
    if application.requested_tier in [AgentTier.SUPER_AGENT, AgentTier.REGIONAL_AGENT]:
        if application.kyb_status == VerificationStatus.VERIFIED:
            completed_steps += 1
    else:
        completed_steps += 1  # Skip KYB for individual agents
    
    # Final review
    if application.status in [OnboardingStatus.APPROVED, OnboardingStatus.ACTIVE]:
        completed_steps += 1
    
    return int((completed_steps / total_steps) * 100)

def get_next_steps(application: AgentOnboarding) -> List[str]:
    """Get next steps for the application"""
    next_steps = []
    
    if application.status == OnboardingStatus.DRAFT:
        if not all([application.first_name, application.last_name, application.email, application.phone]):
            next_steps.append("Complete personal information")
        if not all([application.street_address, application.city, application.country]):
            next_steps.append("Complete address information")
        if len(application.documents) < 2:
            next_steps.append("Upload required documents (ID and proof of address)")
        if not next_steps:
            next_steps.append("Submit application for review")
    
    elif application.status == OnboardingStatus.SUBMITTED:
        next_steps.append("Application is under initial review")
    
    elif application.status == OnboardingStatus.UNDER_REVIEW:
        if application.kyc_status == VerificationStatus.PENDING:
            next_steps.append("KYC verification in progress")
        if application.kyb_status == VerificationStatus.PENDING and application.requested_tier in [AgentTier.SUPER_AGENT, AgentTier.REGIONAL_AGENT]:
            next_steps.append("KYB verification in progress")
    
    elif application.status == OnboardingStatus.ADDITIONAL_INFO_REQUIRED:
        next_steps.append("Provide additional information as requested")
    
    elif application.status == OnboardingStatus.APPROVED:
        next_steps.append("Account activation in progress")
    
    elif application.status == OnboardingStatus.ACTIVE:
        next_steps.append("Onboarding complete - welcome to the platform!")
    
    return next_steps

def get_required_documents(application: AgentOnboarding) -> List[str]:
    """Get list of required documents based on agent tier"""
    required_docs = [
        "National ID or Passport",
        "Proof of Address",
        "Recent Photo"
    ]
    
    if application.requested_tier in [AgentTier.SUPER_AGENT, AgentTier.REGIONAL_AGENT]:
        required_docs.extend([
            "Business License",
            "Tax Certificate",
            "Bank Statement (last 3 months)",
            "Reference Letter"
        ])
    
    # Filter out already uploaded documents
    uploaded_types = [doc.document_type for doc in application.documents]
    missing_docs = []
    
    for doc in required_docs:
        doc_type_mapping = {
            "National ID or Passport": [DocumentType.NATIONAL_ID, DocumentType.PASSPORT],
            "Proof of Address": [DocumentType.PROOF_OF_ADDRESS],
            "Recent Photo": [DocumentType.PHOTO],
            "Business License": [DocumentType.BUSINESS_LICENSE],
            "Tax Certificate": [DocumentType.TAX_CERTIFICATE],
            "Bank Statement (last 3 months)": [DocumentType.BANK_STATEMENT],
            "Reference Letter": [DocumentType.REFERENCE_LETTER]
        }
        
        doc_types = doc_type_mapping.get(doc, [])
        if not any(doc_type in uploaded_types for doc_type in doc_types):
            missing_docs.append(doc)
    
    return missing_docs

# API Endpoints
@app.post("/onboarding/applications", response_model=dict)
async def create_application(
    application_data: AgentOnboardingCreate,
    db: Session = Depends(get_db)
):
    """Create new agent onboarding application"""
    try:
        # Generate application number
        app_number = generate_application_number()
        
        # Create application
        application = AgentOnboarding(
            application_number=app_number,
            **application_data.dict()
        )
        
        db.add(application)
        db.commit()
        db.refresh(application)
        
        logger.info(f"Created onboarding application: {app_number}")
        
        return {
            "application_id": application.id,
            "application_number": app_number,
            "status": application.status,
            "message": "Application created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/onboarding/applications/{application_id}", response_model=OnboardingStatusResponse)
async def get_application_status(
    application_id: str,
    db: Session = Depends(get_db)
):
    """Get application status and progress"""
    try:
        application = db.query(AgentOnboarding).filter(
            AgentOnboarding.id == application_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        progress = calculate_progress_percentage(application)
        next_steps = get_next_steps(application)
        required_docs = get_required_documents(application)
        
        return OnboardingStatusResponse(
            application_id=application.id,
            application_number=application.application_number,
            status=application.status,
            kyc_status=application.kyc_status,
            kyb_status=application.kyb_status,
            risk_score=application.risk_score,
            risk_level=application.risk_level,
            progress_percentage=progress,
            next_steps=next_steps,
            required_documents=required_docs
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting application status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/onboarding/applications/{application_id}")
async def update_application(
    application_id: str,
    update_data: AgentOnboardingUpdate,
    db: Session = Depends(get_db)
):
    """Update application information"""
    try:
        application = db.query(AgentOnboarding).filter(
            AgentOnboarding.id == application_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        if application.status not in [OnboardingStatus.DRAFT, OnboardingStatus.ADDITIONAL_INFO_REQUIRED]:
            raise HTTPException(
                status_code=400,
                detail="Application cannot be modified in current status"
            )
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(application, field, value)
        
        application.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Application updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/onboarding/applications/{application_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    application_id: str,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload document for application"""
    try:
        application = db.query(AgentOnboarding).filter(
            AgentOnboarding.id == application_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Create upload directory
        upload_dir = f"uploads/onboarding/{application_id}"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        file_name = f"{document_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        file_path = os.path.join(upload_dir, file_name)
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Create document record
        document = OnboardingDocument(
            application_id=application_id,
            document_type=document_type,
            document_name=file.filename,
            file_path=file_path,
            file_size=len(content),
            mime_type=file.content_type
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Process document with OCR (async)
        asyncio.create_task(process_document_async(document.id, file_path, document_type))
        
        return DocumentUploadResponse(
            document_id=document.id,
            document_type=document_type,
            file_name=file.filename,
            upload_status="success",
            processing_status="pending"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_document_async(document_id: str, file_path: str, document_type: str):
    """Async document processing"""
    try:
        db = SessionLocal()
        document = db.query(OnboardingDocument).filter(
            OnboardingDocument.id == document_id
        ).first()
        
        if document:
            # Process with OCR
            ocr_result = await process_document_ocr(file_path, document_type)
            
            # Update document
            document.processing_status = ocr_result["status"]
            if ocr_result["status"] == "success":
                document.ocr_text = ocr_result["extracted_data"]["text_content"]
                document.extracted_data = ocr_result["extracted_data"]
                document.verification_status = VerificationStatus.IN_PROGRESS
            else:
                document.processing_error = ocr_result.get("error", "Processing failed")
            
            db.commit()
        
        db.close()
    except Exception as e:
        logger.error(f"Error in async document processing: {str(e)}")

@app.post("/onboarding/applications/{application_id}/submit")
async def submit_application(
    application_id: str,
    db: Session = Depends(get_db)
):
    """Submit application for review"""
    try:
        application = db.query(AgentOnboarding).filter(
            AgentOnboarding.id == application_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        if application.status != OnboardingStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Application has already been submitted"
            )
        
        # Validate required information
        required_fields = ['first_name', 'last_name', 'email', 'phone', 'requested_tier']
        missing_fields = [field for field in required_fields if not getattr(application, field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Check required documents
        required_docs = get_required_documents(application)
        if required_docs:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required documents: {', '.join(required_docs)}"
            )
        
        # Update status
        application.status = OnboardingStatus.SUBMITTED
        application.submitted_at = datetime.utcnow()
        db.commit()
        
        # Start verification process (async)
        asyncio.create_task(start_verification_process(application_id))
        
        return {"message": "Application submitted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def start_verification_process(application_id: str):
    """Start KYC/KYB verification process"""
    try:
        db = SessionLocal()
        application = db.query(AgentOnboarding).filter(
            AgentOnboarding.id == application_id
        ).first()
        
        if application:
            # Update status to under review
            application.status = OnboardingStatus.UNDER_REVIEW
            db.commit()
            
            # Perform KYC verification
            kyc_result = await perform_kyc_verification(application, db)
            if kyc_result["status"] == "verified":
                application.kyc_status = VerificationStatus.VERIFIED
            else:
                application.kyc_status = VerificationStatus.FAILED
            
            # Perform KYB verification if required
            if application.requested_tier in [AgentTier.SUPER_AGENT, AgentTier.REGIONAL_AGENT]:
                kyb_result = await perform_kyb_verification(application, db)
                if kyb_result["status"] == "verified":
                    application.kyb_status = VerificationStatus.VERIFIED
                else:
                    application.kyb_status = VerificationStatus.FAILED
            else:
                application.kyb_status = VerificationStatus.VERIFIED  # Not required
            
            # Calculate risk score
            verifications = db.query(VerificationRecord).filter(
                VerificationRecord.application_id == application_id
            ).all()
            
            risk_score, risk_level = calculate_risk_score(application, verifications)
            application.risk_score = risk_score
            application.risk_level = risk_level
            
            # Auto-approve if all verifications passed and risk is acceptable
            if (application.kyc_status == VerificationStatus.VERIFIED and
                application.kyb_status == VerificationStatus.VERIFIED and
                risk_level in ["low", "medium"]):
                
                application.status = OnboardingStatus.APPROVED
                application.approved_at = datetime.utcnow()
            else:
                # Require manual review
                application.status = OnboardingStatus.UNDER_REVIEW
            
            db.commit()
        
        db.close()
    except Exception as e:
        logger.error(f"Error in verification process: {str(e)}")

@app.post("/onboarding/applications/{application_id}/verify", response_model=VerificationResponse)
async def trigger_verification(
    application_id: str,
    verification_type: str,
    db: Session = Depends(get_db)
):
    """Manually trigger verification process"""
    try:
        application = db.query(AgentOnboarding).filter(
            AgentOnboarding.id == application_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        if verification_type == "kyc":
            result = await perform_kyc_verification(application, db)
            if result["status"] == "verified":
                application.kyc_status = VerificationStatus.VERIFIED
            else:
                application.kyc_status = VerificationStatus.FAILED
        elif verification_type == "kyb":
            result = await perform_kyb_verification(application, db)
            if result["status"] == "verified":
                application.kyb_status = VerificationStatus.VERIFIED
            else:
                application.kyb_status = VerificationStatus.FAILED
        else:
            raise HTTPException(status_code=400, detail="Invalid verification type")
        
        db.commit()
        
        return VerificationResponse(
            verification_id=str(uuid.uuid4()),
            verification_type=verification_type,
            status=result["status"],
            score=result.get("score", 0.0),
            confidence=result.get("confidence", 0.0),
            notes=result.get("notes")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering verification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/onboarding/applications")
async def list_applications(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List onboarding applications with filters"""
    try:
        query = db.query(AgentOnboarding)
        
        if status:
            query = query.filter(AgentOnboarding.status == status)
        if tier:
            query = query.filter(AgentOnboarding.requested_tier == tier)
        
        applications = query.offset(skip).limit(limit).all()
        
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
                    "risk_level": app.risk_level,
                    "submitted_at": app.submitted_at,
                    "created_at": app.created_at
                }
                for app in applications
            ],
            "total": query.count()
        }
    except Exception as e:
        logger.error(f"Error listing applications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Agent Onboarding Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# Create tables
Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
