import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
KYB (Know Your Business) Verification Service
Integrates with Temporal for comprehensive business verification and compliance
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import base64

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("kyb-verification-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import aioredis

# Import screening services
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from kyb_screening_services import (
    SanctionsScreeningService,
    AdverseMediaScreeningService,
    PEPScreeningService
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/kyb_verification")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BusinessType(str, Enum):
    CORPORATION = "corporation"
    LLC = "llc"
    PARTNERSHIP = "partnership"
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    NON_PROFIT = "non_profit"
    TRUST = "trust"
    OTHER = "other"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DOCUMENTS_REQUIRED = "documents_required"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"

class DocumentType(str, Enum):
    ARTICLES_OF_INCORPORATION = "articles_of_incorporation"
    BUSINESS_LICENSE = "business_license"
    TAX_ID_CERTIFICATE = "tax_id_certificate"
    BANK_STATEMENT = "bank_statement"
    UTILITY_BILL = "utility_bill"
    MEMORANDUM_OF_ASSOCIATION = "memorandum_of_association"
    CERTIFICATE_OF_GOOD_STANDING = "certificate_of_good_standing"
    BENEFICIAL_OWNERSHIP_FORM = "beneficial_ownership_form"
    DIRECTOR_RESOLUTION = "director_resolution"
    POWER_OF_ATTORNEY = "power_of_attorney"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class BusinessInfo:
    legal_name: str
    trade_name: Optional[str]
    business_type: BusinessType
    registration_number: Optional[str]
    tax_id: Optional[str]
    incorporation_date: Optional[datetime]
    incorporation_country: str
    incorporation_state: Optional[str]
    business_address: Dict[str, str]
    mailing_address: Optional[Dict[str, str]]
    phone: Optional[str]
    email: Optional[str]
    website: Optional[str]
    industry: Optional[str]
    description: Optional[str]

@dataclass
class BeneficialOwner:
    first_name: str
    last_name: str
    date_of_birth: datetime
    nationality: str
    ownership_percentage: float
    position: Optional[str]
    address: Dict[str, str]
    id_document_type: str
    id_document_number: str
    is_politically_exposed: bool = False

@dataclass
class AuthorizedRepresentative:
    first_name: str
    last_name: str
    position: str
    email: str
    phone: str
    address: Dict[str, str]
    id_document_type: str
    id_document_number: str

class KYBVerification(Base):
    __tablename__ = "kyb_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(String, nullable=False, unique=True, index=True)
    temporal_workflow_id = Column(String, index=True)
    business_info = Column(JSON, nullable=False)
    beneficial_owners = Column(JSON)
    authorized_representatives = Column(JSON)
    status = Column(String, default=VerificationStatus.PENDING.value, index=True)
    risk_level = Column(String, index=True)
    risk_score = Column(Float)
    verification_notes = Column(Text)
    documents_required = Column(JSON)
    documents_submitted = Column(JSON)
    compliance_checks = Column(JSON)
    sanctions_screening = Column(JSON)
    adverse_media_screening = Column(JSON)
    pep_screening = Column(JSON)  # Politically Exposed Persons
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = Column(DateTime)
    approved_by = Column(String)
    rejected_at = Column(DateTime)
    rejected_by = Column(String)
    rejection_reason = Column(Text)

class KYBDocument(Base):
    __tablename__ = "kyb_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    ocr_extracted_text = Column(Text)
    ocr_confidence = Column(Float)
    document_analysis = Column(JSON)
    is_verified = Column(Boolean, default=False)
    verification_notes = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime)
    verified_by = Column(String)

class KYBWorkflowEvent(Base):
    __tablename__ = "kyb_workflow_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON)
    workflow_event_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    processed = Column(Boolean, default=False)

# Create tables
Base.metadata.create_all(bind=engine)

class KYBVerificationService:
    def __init__(self):
        self.redis_client = None
        self.temporal_api_url = os.getenv("TEMPORAL_API_URL", "http://localhost:7233")
        self.temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
        self.ocr_service_url = os.getenv("OCR_SERVICE_URL", "http://localhost:8014")
        
        # Initialize screening services
        self.sanctions_service = SanctionsScreeningService()
        self.adverse_media_service = AdverseMediaScreeningService()
        self.pep_service = PEPScreeningService()
        
        # Risk scoring weights
        self.risk_weights = {
            "business_age": 0.15,
            "ownership_transparency": 0.20,
            "sanctions_hits": 0.25,
            "adverse_media": 0.15,
            "pep_exposure": 0.10,
            "document_quality": 0.10,
            "industry_risk": 0.05
        }
    
    async def initialize(self):
        """Initialize the KYB verification service"""
        try:
            # Initialize Redis for caching
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            logger.info("KYB Verification Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize KYB Verification Service: {e}")
            self.redis_client = None
    
    async def start_kyb_verification(self, business_info: BusinessInfo,
                                   beneficial_owners: List[BeneficialOwner],
                                   authorized_representatives: List[AuthorizedRepresentative],
                                   initiated_by: str) -> str:
        """Start KYB verification process"""
        db = SessionLocal()
        try:
            business_id = str(uuid.uuid4())
            
            temporal_workflow_id = await self._create_temporal_workflow(
                business_id, business_info, beneficial_owners, authorized_representatives
            )
            
            verification = KYBVerification(
                business_id=business_id,
                temporal_workflow_id=temporal_workflow_id,
                business_info=asdict(business_info),
                beneficial_owners=[asdict(bo) for bo in beneficial_owners],
                authorized_representatives=[asdict(ar) for ar in authorized_representatives],
                status=VerificationStatus.PENDING.value,
                documents_required=self._get_required_documents(business_info.business_type),
                documents_submitted=[],
                compliance_checks={},
                sanctions_screening={},
                adverse_media_screening={},
                pep_screening={}
            )
            
            db.add(verification)
            db.commit()
            db.refresh(verification)
            
            # Start background verification processes
            asyncio.create_task(self._perform_initial_screening(str(verification.id)))
            
            return business_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to start KYB verification: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def _create_temporal_workflow(self, business_id: str, business_info: BusinessInfo,
                                       beneficial_owners: List[BeneficialOwner],
                                       authorized_representatives: List[AuthorizedRepresentative]) -> str:
        """Create workflow via Temporal"""
        try:
            async with httpx.AsyncClient() as client:
                workflow_id = f"kyb-{business_id[:8]}-{uuid.uuid4().hex[:8]}"
                workflow_data = {
                    "workflowId": workflow_id,
                    "workflowType": {"name": "kyb-verification"},
                    "taskQueue": {"name": "kyb-verification"},
                    "input": {
                        "payloads": [{
                            "data": {
                                "businessId": business_id,
                                "businessInformation": asdict(business_info),
                                "beneficialOwners": [asdict(bo) for bo in beneficial_owners],
                                "authorizedRepresentatives": [asdict(ar) for ar in authorized_representatives],
                                "webhookUrl": f"{os.getenv('WEBHOOK_BASE_URL', 'http://localhost:8015')}/kyb/webhook"
                            }
                        }]
                    }
                }
                
                response = await client.post(
                    f"{self.temporal_api_url}/api/v1/namespaces/{self.temporal_namespace}/workflows",
                    json=workflow_data,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                
                if response.status_code in (200, 201):
                    return workflow_id
                else:
                    logger.error(f"Failed to create Temporal workflow: {response.text}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Error creating Temporal workflow: {e}")
            return ""
    
    def _get_required_documents(self, business_type: BusinessType) -> List[str]:
        """Get required documents based on business type"""
        base_documents = [
            DocumentType.ARTICLES_OF_INCORPORATION.value,
            DocumentType.BUSINESS_LICENSE.value,
            DocumentType.TAX_ID_CERTIFICATE.value,
            DocumentType.BANK_STATEMENT.value,
            DocumentType.BENEFICIAL_OWNERSHIP_FORM.value
        ]
        
        if business_type == BusinessType.CORPORATION:
            base_documents.extend([
                DocumentType.CERTIFICATE_OF_GOOD_STANDING.value,
                DocumentType.DIRECTOR_RESOLUTION.value
            ])
        elif business_type == BusinessType.LLC:
            base_documents.append(DocumentType.MEMORANDUM_OF_ASSOCIATION.value)
        
        return base_documents
    
    async def _perform_initial_screening(self, verification_id: str):
        """Perform initial compliance screening"""
        db = SessionLocal()
        try:
            verification = db.query(KYBVerification).filter(
                KYBVerification.id == verification_id
            ).first()
            
            if not verification:
                return
            
            # Update status
            verification.status = VerificationStatus.IN_PROGRESS.value
            db.commit()
            
            # Perform sanctions screening
            sanctions_results = await self._perform_sanctions_screening(verification)
            verification.sanctions_screening = sanctions_results
            
            # Perform adverse media screening
            adverse_media_results = await self._perform_adverse_media_screening(verification)
            verification.adverse_media_screening = adverse_media_results
            
            # Perform PEP screening
            pep_results = await self._perform_pep_screening(verification)
            verification.pep_screening = pep_results
            
            # Calculate initial risk score
            risk_score = await self._calculate_risk_score(verification)
            verification.risk_score = risk_score
            verification.risk_level = self._get_risk_level(risk_score)
            
            # Update status based on screening results
            if self._requires_manual_review(verification):
                verification.status = VerificationStatus.UNDER_REVIEW.value
            else:
                verification.status = VerificationStatus.DOCUMENTS_REQUIRED.value
            
            db.commit()
            
            await self._update_temporal_workflow(verification.temporal_workflow_id, {
                "status": verification.status,
                "riskScore": verification.risk_score,
                "riskLevel": verification.risk_level,
                "screeningResults": {
                    "sanctions": sanctions_results,
                    "adverseMedia": adverse_media_results,
                    "pep": pep_results
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to perform initial screening: {e}")
        finally:
            db.close()
    
    async def _perform_sanctions_screening(self, verification: KYBVerification) -> Dict[str, Any]:
        """Perform sanctions screening for business and beneficial owners"""
        try:
            results = {
                "business": {"hits": [], "checked_at": datetime.utcnow().isoformat()},
                "beneficial_owners": []
            }
            
            # Screen business entity
            business_info = verification.business_info
            business_hits = await self._screen_entity_sanctions(
                business_info.get("legal_name", ""),
                business_info.get("incorporation_country", ""),
                entity_type="business"
            )
            results["business"]["hits"] = business_hits
            
            # Screen beneficial owners
            for bo in verification.beneficial_owners or []:
                bo_hits = await self._screen_entity_sanctions(
                    f"{bo.get('first_name', '')} {bo.get('last_name', '')}",
                    bo.get("nationality", ""),
                    entity_type="individual"
                )
                results["beneficial_owners"].append({
                    "name": f"{bo.get('first_name', '')} {bo.get('last_name', '')}",
                    "hits": bo_hits,
                    "checked_at": datetime.utcnow().isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Sanctions screening failed: {e}")
            return {"error": str(e)}
    
    async def _screen_entity_sanctions(self, name: str, country: str, entity_type: str) -> List[Dict[str, Any]]:
        """Screen entity against sanctions lists"""
        return await self.sanctions_service.screen_entity(name, country, entity_type)
    
    async def _perform_adverse_media_screening(self, verification: KYBVerification) -> Dict[str, Any]:
        """Perform adverse media screening"""
        try:
            results = {
                "business": {"articles": [], "checked_at": datetime.utcnow().isoformat()},
                "beneficial_owners": []
            }
            
            # Screen business
            business_info = verification.business_info
            business_articles = await self._screen_adverse_media(
                business_info.get("legal_name", ""),
                entity_type="business"
            )
            results["business"]["articles"] = business_articles
            
            # Screen beneficial owners
            for bo in verification.beneficial_owners or []:
                bo_articles = await self._screen_adverse_media(
                    f"{bo.get('first_name', '')} {bo.get('last_name', '')}",
                    entity_type="individual"
                )
                results["beneficial_owners"].append({
                    "name": f"{bo.get('first_name', '')} {bo.get('last_name', '')}",
                    "articles": bo_articles,
                    "checked_at": datetime.utcnow().isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Adverse media screening failed: {e}")
            return {"error": str(e)}
    
    async def _screen_adverse_media(self, name: str, entity_type: str) -> List[Dict[str, Any]]:
        """Screen for adverse media mentions"""
        return await self.adverse_media_service.screen_entity(name, entity_type)
    
    async def _perform_pep_screening(self, verification: KYBVerification) -> Dict[str, Any]:
        """Perform Politically Exposed Persons screening"""
        try:
            results = {"beneficial_owners": []}
            
            # Screen beneficial owners for PEP status
            for bo in verification.beneficial_owners or []:
                pep_status = await self._check_pep_status(
                    f"{bo.get('first_name', '')} {bo.get('last_name', '')}",
                    bo.get("nationality", "")
                )
                results["beneficial_owners"].append({
                    "name": f"{bo.get('first_name', '')} {bo.get('last_name', '')}",
                    "is_pep": pep_status.get("is_pep", False),
                    "pep_details": pep_status.get("details", {}),
                    "checked_at": datetime.utcnow().isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"PEP screening failed: {e}")
            return {"error": str(e)}
    
    async def _check_pep_status(self, name: str, nationality: str) -> Dict[str, Any]:
        """Check if person is politically exposed"""
        return await self.pep_service.check_pep_status(name, nationality)
    
    async def _calculate_risk_score(self, verification: KYBVerification) -> float:
        """Calculate overall risk score"""
        try:
            score = 0.0
            
            # Business age factor
            business_info = verification.business_info
            if business_info.get("incorporation_date"):
                incorporation_date = datetime.fromisoformat(business_info["incorporation_date"])
                business_age_years = (datetime.utcnow() - incorporation_date).days / 365
                age_score = max(0, min(1, business_age_years / 5))  # 5+ years = low risk
                score += (1 - age_score) * self.risk_weights["business_age"]
            
            # Ownership transparency
            beneficial_owners = verification.beneficial_owners or []
            total_ownership = sum(bo.get("ownership_percentage", 0) for bo in beneficial_owners)
            transparency_score = min(1, total_ownership / 100)
            score += (1 - transparency_score) * self.risk_weights["ownership_transparency"]
            
            # Sanctions hits
            sanctions_results = verification.sanctions_screening or {}
            business_hits = len(sanctions_results.get("business", {}).get("hits", []))
            bo_hits = sum(len(bo.get("hits", [])) for bo in sanctions_results.get("beneficial_owners", []))
            sanctions_score = min(1, (business_hits + bo_hits) / 5)  # Normalize to 0-1
            score += sanctions_score * self.risk_weights["sanctions_hits"]
            
            # Adverse media
            adverse_media = verification.adverse_media_screening or {}
            business_articles = len(adverse_media.get("business", {}).get("articles", []))
            bo_articles = sum(len(bo.get("articles", [])) for bo in adverse_media.get("beneficial_owners", []))
            media_score = min(1, (business_articles + bo_articles) / 10)
            score += media_score * self.risk_weights["adverse_media"]
            
            # PEP exposure
            pep_results = verification.pep_screening or {}
            pep_count = sum(1 for bo in pep_results.get("beneficial_owners", []) if bo.get("is_pep", False))
            pep_score = min(1, pep_count / len(beneficial_owners)) if beneficial_owners else 0
            score += pep_score * self.risk_weights["pep_exposure"]
            
            # Industry risk (simplified)
            industry = business_info.get("industry", "").lower()
            high_risk_industries = ["cryptocurrency", "money_services", "gambling", "adult_entertainment"]
            industry_score = 1 if any(risk_industry in industry for risk_industry in high_risk_industries) else 0.3
            score += industry_score * self.risk_weights["industry_risk"]
            
            return min(1.0, score)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"Risk score calculation failed: {e}")
            return 0.5  # Default medium risk
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level"""
        if risk_score <= 0.25:
            return RiskLevel.LOW.value
        elif risk_score <= 0.5:
            return RiskLevel.MEDIUM.value
        elif risk_score <= 0.75:
            return RiskLevel.HIGH.value
        else:
            return RiskLevel.VERY_HIGH.value
    
    def _requires_manual_review(self, verification: KYBVerification) -> bool:
        """Determine if verification requires manual review"""
        # Check for sanctions hits
        sanctions_results = verification.sanctions_screening or {}
        if sanctions_results.get("business", {}).get("hits") or \
           any(bo.get("hits") for bo in sanctions_results.get("beneficial_owners", [])):
            return True
        
        # Check for PEP exposure
        pep_results = verification.pep_screening or {}
        if any(bo.get("is_pep", False) for bo in pep_results.get("beneficial_owners", [])):
            return True
        
        # Check risk score
        if verification.risk_score and verification.risk_score > 0.7:
            return True
        
        return False
    
    async def upload_document(self, business_id: str, document_type: DocumentType,
                            file: UploadFile, uploaded_by: str) -> str:
        """Upload and process KYB document"""
        db = SessionLocal()
        try:
            # Get verification record
            verification = db.query(KYBVerification).filter(
                KYBVerification.business_id == business_id
            ).first()
            
            if not verification:
                raise HTTPException(status_code=404, detail="Verification not found")
            
            # Save file
            file_id = str(uuid.uuid4())
            file_extension = os.path.splitext(file.filename)[1]
            file_name = f"{file_id}{file_extension}"
            
            documents_dir = os.path.join(os.path.dirname(__file__), 'documents')
            os.makedirs(documents_dir, exist_ok=True)
            file_path = os.path.join(documents_dir, file_name)
            
            # Save uploaded file
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # Create document record
            document = KYBDocument(
                verification_id=verification.id,
                document_type=document_type.value,
                file_name=file.filename,
                file_path=file_path,
                file_size=len(content),
                mime_type=file.content_type
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            # Process document with OCR
            asyncio.create_task(self._process_document_ocr(str(document.id)))
            
            # Update verification status
            await self._update_verification_documents(verification, document_type.value)
            
            return str(document.id)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to upload document: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def _process_document_ocr(self, document_id: str):
        """Process document with OCR extraction"""
        db = SessionLocal()
        try:
            document = db.query(KYBDocument).filter(KYBDocument.id == document_id).first()
            if not document:
                return
            
            # Call OCR service
            ocr_result = await self._extract_text_with_ocr(document.file_path)
            
            # Update document with OCR results
            document.ocr_extracted_text = ocr_result.get("text", "")
            document.ocr_confidence = ocr_result.get("confidence", 0.0)
            document.document_analysis = ocr_result.get("analysis", {})
            
            db.commit()
            
            # Analyze document content
            analysis_result = await self._analyze_document_content(document)
            
            # Update verification if document is verified
            if analysis_result.get("is_valid", False):
                document.is_verified = True
                document.verification_notes = analysis_result.get("notes", "")
                document.verified_at = datetime.utcnow()
                db.commit()
                
                # Check if all required documents are submitted
                await self._check_verification_completion(str(document.verification_id))
            
        except Exception as e:
            logger.error(f"Failed to process document OCR: {e}")
        finally:
            db.close()
    
    async def _extract_text_with_ocr(self, file_path: str) -> Dict[str, Any]:
        """Extract text from document using OCR service"""
        try:
            async with httpx.AsyncClient() as client:
                with open(file_path, 'rb') as f:
                    files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
                    
                    response = await client.post(
                        f"{self.ocr_service_url}/extract-text",
                        files=files,
                        timeout=60.0
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                    else:
                        logger.error(f"OCR service error: {response.text}")
                        return {"text": "", "confidence": 0.0, "analysis": {}}
                        
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {"text": "", "confidence": 0.0, "analysis": {}}
    
    async def _analyze_document_content(self, document: KYBDocument) -> Dict[str, Any]:
        """Analyze document content for validity"""
        try:
            text = document.ocr_extracted_text or ""
            document_type = document.document_type
            
            analysis = {
                "is_valid": False,
                "confidence": document.ocr_confidence or 0.0,
                "notes": "",
                "extracted_fields": {}
            }
            
            # Basic validation based on document type
            if document_type == DocumentType.ARTICLES_OF_INCORPORATION.value:
                if "articles of incorporation" in text.lower() or "certificate of incorporation" in text.lower():
                    analysis["is_valid"] = True
                    analysis["notes"] = "Valid articles of incorporation document"
                    
                    # Extract key fields
                    analysis["extracted_fields"] = self._extract_incorporation_fields(text)
            
            elif document_type == DocumentType.BUSINESS_LICENSE.value:
                if "license" in text.lower() and ("business" in text.lower() or "trade" in text.lower()):
                    analysis["is_valid"] = True
                    analysis["notes"] = "Valid business license document"
                    
                    analysis["extracted_fields"] = self._extract_license_fields(text)
            
            elif document_type == DocumentType.BANK_STATEMENT.value:
                if "statement" in text.lower() and ("bank" in text.lower() or "account" in text.lower()):
                    analysis["is_valid"] = True
                    analysis["notes"] = "Valid bank statement document"
                    
                    analysis["extracted_fields"] = self._extract_bank_statement_fields(text)
            
            # Add more document type validations as needed
            
            return analysis
            
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return {"is_valid": False, "confidence": 0.0, "notes": f"Analysis failed: {e}"}
    
    def _extract_incorporation_fields(self, text: str) -> Dict[str, Any]:
        """Extract fields from articles of incorporation"""
        fields = {}
        
        # Simple regex-based extraction (would be more sophisticated in production)
        import re
        
        # Company name
        name_match = re.search(r"(?:company name|corporation name|name of corporation)[:\s]+([^\n]+)", text, re.IGNORECASE)
        if name_match:
            fields["company_name"] = name_match.group(1).strip()
        
        # Incorporation date
        date_match = re.search(r"(?:incorporated|date of incorporation)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text, re.IGNORECASE)
        if date_match:
            fields["incorporation_date"] = date_match.group(1)
        
        # State of incorporation
        state_match = re.search(r"(?:state of|incorporated in)[:\s]+([^\n,]+)", text, re.IGNORECASE)
        if state_match:
            fields["state"] = state_match.group(1).strip()
        
        return fields
    
    def _extract_license_fields(self, text: str) -> Dict[str, Any]:
        """Extract fields from business license"""
        fields = {}
        
        import re
        
        # License number
        license_match = re.search(r"(?:license number|license no)[:\s#]+([A-Z0-9-]+)", text, re.IGNORECASE)
        if license_match:
            fields["license_number"] = license_match.group(1)
        
        # Expiration date
        exp_match = re.search(r"(?:expires|expiration date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text, re.IGNORECASE)
        if exp_match:
            fields["expiration_date"] = exp_match.group(1)
        
        return fields
    
    def _extract_bank_statement_fields(self, text: str) -> Dict[str, Any]:
        """Extract fields from bank statement"""
        fields = {}
        
        import re
        
        # Account number
        account_match = re.search(r"(?:account number|account no)[:\s#]+([0-9-]+)", text, re.IGNORECASE)
        if account_match:
            fields["account_number"] = account_match.group(1)
        
        # Statement period
        period_match = re.search(r"(?:statement period|period)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*(?:to|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})", text, re.IGNORECASE)
        if period_match:
            fields["statement_period"] = {
                "from": period_match.group(1),
                "to": period_match.group(2)
            }
        
        return fields
    
    async def _update_verification_documents(self, verification: KYBVerification, document_type: str):
        """Update verification with submitted document"""
        db = SessionLocal()
        try:
            documents_submitted = verification.documents_submitted or []
            if document_type not in documents_submitted:
                documents_submitted.append(document_type)
                verification.documents_submitted = documents_submitted
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update verification documents: {e}")
        finally:
            db.close()
    
    async def _check_verification_completion(self, verification_id: str):
        """Check if verification is complete and update status"""
        db = SessionLocal()
        try:
            verification = db.query(KYBVerification).filter(
                KYBVerification.id == verification_id
            ).first()
            
            if not verification:
                return
            
            required_docs = set(verification.documents_required or [])
            submitted_docs = set(verification.documents_submitted or [])
            
            if required_docs.issubset(submitted_docs):
                # All required documents submitted
                if verification.risk_level in [RiskLevel.LOW.value, RiskLevel.MEDIUM.value] and \
                   not self._requires_manual_review(verification):
                    # Auto-approve low/medium risk with no red flags
                    verification.status = VerificationStatus.APPROVED.value
                    verification.approved_at = datetime.utcnow()
                    verification.approved_by = "system"
                else:
                    # Requires manual review
                    verification.status = VerificationStatus.UNDER_REVIEW.value
                
                db.commit()
                
                await self._update_temporal_workflow(verification.temporal_workflow_id, {
                    "status": verification.status,
                    "documentsComplete": True
                })
                
        except Exception as e:
            logger.error(f"Failed to check verification completion: {e}")
        finally:
            db.close()
    
    async def _update_temporal_workflow(self, workflow_id: str, update_data: Dict[str, Any]):
        """Update Temporal workflow via signal"""
        if not workflow_id:
            return
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.temporal_api_url}/api/v1/namespaces/{self.temporal_namespace}/workflows/{workflow_id}/signal",
                    json={
                        "signalName": "workflow_update",
                        "input": {"payloads": [{"data": update_data}]}
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                
                if response.status_code not in (200, 201):
                    logger.error(f"Failed to signal Temporal workflow: {response.text}")
                    
        except Exception as e:
            logger.error(f"Error signaling Temporal workflow: {e}")
    
    async def get_verification_status(self, business_id: str) -> Dict[str, Any]:
        """Get KYB verification status"""
        db = SessionLocal()
        try:
            verification = db.query(KYBVerification).filter(
                KYBVerification.business_id == business_id
            ).first()
            
            if not verification:
                raise HTTPException(status_code=404, detail="Verification not found")
            
            # Get submitted documents
            documents = db.query(KYBDocument).filter(
                KYBDocument.verification_id == verification.id
            ).all()
            
            document_status = []
            for doc in documents:
                document_status.append({
                    "id": str(doc.id),
                    "type": doc.document_type,
                    "file_name": doc.file_name,
                    "is_verified": doc.is_verified,
                    "uploaded_at": doc.uploaded_at.isoformat(),
                    "verification_notes": doc.verification_notes
                })
            
            return {
                "business_id": verification.business_id,
                "status": verification.status,
                "risk_level": verification.risk_level,
                "risk_score": verification.risk_score,
                "documents_required": verification.documents_required,
                "documents_submitted": verification.documents_submitted,
                "documents_status": document_status,
                "compliance_checks": verification.compliance_checks,
                "sanctions_screening": verification.sanctions_screening,
                "adverse_media_screening": verification.adverse_media_screening,
                "pep_screening": verification.pep_screening,
                "verification_notes": verification.verification_notes,
                "created_at": verification.created_at.isoformat(),
                "updated_at": verification.updated_at.isoformat(),
                "approved_at": verification.approved_at.isoformat() if verification.approved_at else None,
                "rejected_at": verification.rejected_at.isoformat() if verification.rejected_at else None,
                "rejection_reason": verification.rejection_reason
            }
            
        except Exception as e:
            logger.error(f"Failed to get verification status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def approve_verification(self, business_id: str, approved_by: str, notes: str = None) -> bool:
        """Approve KYB verification"""
        db = SessionLocal()
        try:
            verification = db.query(KYBVerification).filter(
                KYBVerification.business_id == business_id
            ).first()
            
            if not verification:
                raise HTTPException(status_code=404, detail="Verification not found")
            
            verification.status = VerificationStatus.APPROVED.value
            verification.approved_at = datetime.utcnow()
            verification.approved_by = approved_by
            if notes:
                verification.verification_notes = notes
            
            db.commit()
            
            await self._update_temporal_workflow(verification.temporal_workflow_id, {
                "status": "approved",
                "approvedBy": approved_by,
                "approvedAt": datetime.utcnow().isoformat(),
                "notes": notes
            })
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to approve verification: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def reject_verification(self, business_id: str, rejected_by: str, reason: str) -> bool:
        """Reject KYB verification"""
        db = SessionLocal()
        try:
            verification = db.query(KYBVerification).filter(
                KYBVerification.business_id == business_id
            ).first()
            
            if not verification:
                raise HTTPException(status_code=404, detail="Verification not found")
            
            verification.status = VerificationStatus.REJECTED.value
            verification.rejected_at = datetime.utcnow()
            verification.rejected_by = rejected_by
            verification.rejection_reason = reason
            
            db.commit()
            
            await self._update_temporal_workflow(verification.temporal_workflow_id, {
                "status": "rejected",
                "rejectedBy": rejected_by,
                "rejectedAt": datetime.utcnow().isoformat(),
                "rejectionReason": reason
            })
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reject verification: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def handle_workflow_webhook(self, webhook_data: Dict[str, Any]):
        """Handle webhook from Temporal workflow"""
        try:
            workflow_id = webhook_data.get("workflowId")
            event_type = webhook_data.get("eventName")
            event_data = webhook_data.get("data", {})
            
            # Find verification by workflow ID
            db = SessionLocal()
            verification = db.query(KYBVerification).filter(
                KYBVerification.temporal_workflow_id == workflow_id
            ).first()
            
            if not verification:
                logger.warning(f"Verification not found for workflow ID: {workflow_id}")
                return
            
            # Create workflow event record
            workflow_event = KYBWorkflowEvent(
                verification_id=verification.id,
                event_type=event_type,
                event_data=event_data,
                workflow_event_id=webhook_data.get("id")
            )
            
            db.add(workflow_event)
            db.commit()
            
            # Process event based on type
            if event_type == "workflow.completed":
                await self._handle_workflow_completed(verification, event_data)
            elif event_type == "workflow.failed":
                await self._handle_workflow_failed(verification, event_data)
            elif event_type == "document.processed":
                await self._handle_document_processed(verification, event_data)
            
            db.close()
            
        except Exception as e:
            logger.error(f"Failed to handle workflow webhook: {e}")
    
    async def _handle_workflow_completed(self, verification: KYBVerification, event_data: Dict[str, Any]):
        """Handle workflow completion from Temporal"""
        logger.info(f"Workflow completed for verification {verification.business_id}")
    
    async def _handle_workflow_failed(self, verification: KYBVerification, event_data: Dict[str, Any]):
        """Handle workflow failure from Temporal"""
        logger.error(f"Workflow failed for verification {verification.business_id}: {event_data}")
    
    async def _handle_document_processed(self, verification: KYBVerification, event_data: Dict[str, Any]):
        """Handle document processing event from Temporal"""
        logger.info(f"Document processed for verification {verification.business_id}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        db = SessionLocal()
        try:
            # Check database connection
            db.execute("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False
        finally:
            db.close()
        
        # Check Redis connection
        redis_healthy = False
        if self.redis_client:
            try:
                await self.redis_client.ping()
                redis_healthy = True
            except Exception:
                redis_healthy = False
        
        temporal_healthy = False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.temporal_api_url}/api/v1/namespaces/{self.temporal_namespace}",
                    timeout=10.0
                )
                temporal_healthy = response.status_code == 200
        except Exception:
            temporal_healthy = False
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "kyb-verification-service",
            "version": "2.0.0",
            "components": {
                "database": db_healthy,
                "redis": redis_healthy,
                "temporal": temporal_healthy,
            }
        }

# FastAPI application
app = FastAPI(title="KYB Verification Service", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
kyb_service = KYBVerificationService()

# Pydantic models for API
class BusinessInfoModel(BaseModel):
    legal_name: str
    trade_name: Optional[str] = None
    business_type: BusinessType
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    incorporation_date: Optional[datetime] = None
    incorporation_country: str
    incorporation_state: Optional[str] = None
    business_address: Dict[str, str]
    mailing_address: Optional[Dict[str, str]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None

class BeneficialOwnerModel(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: datetime
    nationality: str
    ownership_percentage: float = Field(..., ge=0, le=100)
    position: Optional[str] = None
    address: Dict[str, str]
    id_document_type: str
    id_document_number: str
    is_politically_exposed: bool = False

class AuthorizedRepresentativeModel(BaseModel):
    first_name: str
    last_name: str
    position: str
    email: str
    phone: str
    address: Dict[str, str]
    id_document_type: str
    id_document_number: str

class KYBVerificationRequest(BaseModel):
    business_info: BusinessInfoModel
    beneficial_owners: List[BeneficialOwnerModel]
    authorized_representatives: List[AuthorizedRepresentativeModel]
    initiated_by: str

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await kyb_service.initialize()

@app.post("/start-verification")
async def start_kyb_verification(request: KYBVerificationRequest):
    """Start KYB verification process"""
    business_info = BusinessInfo(**request.business_info.dict())
    beneficial_owners = [BeneficialOwner(**bo.dict()) for bo in request.beneficial_owners]
    authorized_reps = [AuthorizedRepresentative(**ar.dict()) for ar in request.authorized_representatives]
    
    business_id = await kyb_service.start_kyb_verification(
        business_info, beneficial_owners, authorized_reps, request.initiated_by
    )
    
    return {"business_id": business_id, "status": "verification_started"}

@app.post("/upload-document/{business_id}")
async def upload_document(
    business_id: str,
    document_type: DocumentType,
    uploaded_by: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload KYB document"""
    document_id = await kyb_service.upload_document(business_id, document_type, file, uploaded_by)
    return {"document_id": document_id, "status": "uploaded"}

@app.get("/verification/{business_id}/status")
async def get_verification_status(business_id: str):
    """Get KYB verification status"""
    return await kyb_service.get_verification_status(business_id)

@app.post("/verification/{business_id}/approve")
async def approve_verification(
    business_id: str,
    approved_by: str = Form(...),
    notes: Optional[str] = Form(None)
):
    """Approve KYB verification"""
    success = await kyb_service.approve_verification(business_id, approved_by, notes)
    return {"success": success, "status": "approved"}

@app.post("/verification/{business_id}/reject")
async def reject_verification(
    business_id: str,
    rejected_by: str = Form(...),
    reason: str = Form(...)
):
    """Reject KYB verification"""
    success = await kyb_service.reject_verification(business_id, rejected_by, reason)
    return {"success": success, "status": "rejected"}

@app.post("/webhook")
async def workflow_webhook(webhook_data: Dict[str, Any]):
    """Handle Temporal workflow webhook"""
    await kyb_service.handle_workflow_webhook(webhook_data)
    return {"status": "processed"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await kyb_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8015)
