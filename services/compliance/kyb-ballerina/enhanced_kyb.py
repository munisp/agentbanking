"""
Enhanced KYB Service with DeepSeek OCR + Docling Integration
Automated business document parsing and verification
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path
import sys

# Add document processing path
sys.path.append(str(Path(__file__).parent.parent.parent / "document-processing/docling-service"))
from integrated_processor import IntegratedDocumentProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Enhanced KYB Service", version="2.0.0")

class BusinessType(str, Enum):
    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    PRIVATE_LIMITED = "private_limited"
    PUBLIC_LIMITED = "public_limited"
    NGO = "ngo"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class KYBDocumentType(str, Enum):
    BUSINESS_REGISTRATION = "business_registration"
    ARTICLES_OF_INCORPORATION = "articles_of_incorporation"
    MEMORANDUM_OF_ASSOCIATION = "memorandum_of_association"
    TAX_CERTIFICATE = "tax_certificate"
    BUSINESS_LICENSE = "business_license"

class KYBVerificationResult(BaseModel):
    verification_id: str
    business_id: str
    status: VerificationStatus
    risk_level: RiskLevel
    confidence_score: float
    extracted_data: Dict
    document_analysis: Dict
    directors: List[Dict]
    shareholders: List[Dict]
    issues_found: List[str]
    verified_at: Optional[str]

class EnhancedKYBService:
    """Enhanced KYB service with document parsing"""
    
    def __init__(self):
        # Initialize document processor
        self.doc_processor = IntegratedDocumentProcessor(
            use_deepseek=True,
            use_gpu=True
        )
        
        logger.info("Enhanced KYB Service initialized with DeepSeek OCR")
    
    async def verify_business_document(
        self,
        business_id: str,
        document_path: Path,
        document_type: KYBDocumentType,
        provided_data: Dict
    ) -> KYBVerificationResult:
        """
        Verify business document with automated parsing
        
        Args:
            business_id: Business identifier
            document_path: Path to document
            document_type: Type of business document
            provided_data: Business data provided by user
        
        Returns:
            KYBVerificationResult
        """
        verification_id = f"kyb_{business_id}_{datetime.utcnow().timestamp()}"
        
        try:
            # Step 1: Extract business data using DeepSeek OCR + Docling
            logger.info(f"Parsing {document_type} for business {business_id}")
            extracted_data = await self.doc_processor.extract_kyb_data(
                document_path,
                document_type.value
            )
            
            # Step 2: Analyze document structure
            document_analysis = await self._analyze_document_structure(
                document_path,
                document_type
            )
            
            # Step 3: Extract directors and shareholders
            directors = extracted_data.get("directors", [])
            shareholders = extracted_data.get("shareholders", [])
            
            # Step 4: Validate extracted data
            validation_results = self._validate_business_data(
                extracted_data,
                provided_data,
                document_type
            )
            
            # Step 5: Calculate confidence and risk
            confidence_score = extracted_data.get("confidence", 0.0)
            risk_level = self._calculate_risk_level(
                confidence_score,
                validation_results,
                directors,
                shareholders
            )
            
            # Step 6: Determine status
            status = self._determine_status(
                confidence_score,
                validation_results,
                risk_level
            )
            
            # Step 7: Identify issues
            issues_found = self._identify_issues(validation_results)
            
            # Step 8: Set verification timestamp
            verified_at = datetime.utcnow().isoformat() if status == VerificationStatus.VERIFIED else None
            
            result = KYBVerificationResult(
                verification_id=verification_id,
                business_id=business_id,
                status=status,
                risk_level=risk_level,
                confidence_score=confidence_score,
                extracted_data=extracted_data,
                document_analysis=document_analysis,
                directors=directors,
                shareholders=shareholders,
                issues_found=issues_found,
                verified_at=verified_at
            )
            
            logger.info(
                f"KYB verification complete: {verification_id}, "
                f"status: {status}, confidence: {confidence_score:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"KYB verification error: {e}")
            raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    
    async def _analyze_document_structure(
        self,
        document_path: Path,
        document_type: KYBDocumentType
    ) -> Dict:
        """Analyze document structure and completeness"""
        
        # Process document to get full analysis
        result = await self.doc_processor.process_document(
            document_path,
            document_type=document_type.value,
            extract_entities=True,
            extract_tables=True
        )
        
        analysis = {
            "page_count": result.get("page_count", 1),
            "has_tables": len(result.get("tables", [])) > 0,
            "table_count": len(result.get("tables", [])),
            "entity_count": len(result.get("entities", [])),
            "text_length": len(result.get("combined_text", "")),
            "markdown_available": bool(result.get("markdown")),
            "structure_quality": "good"
        }
        
        # Assess structure quality
        if analysis["page_count"] < 1:
            analysis["structure_quality"] = "poor"
        elif analysis["entity_count"] < 3:
            analysis["structure_quality"] = "acceptable"
        elif analysis["entity_count"] >= 5 and analysis["has_tables"]:
            analysis["structure_quality"] = "excellent"
        
        return analysis
    
    def _validate_business_data(
        self,
        extracted_data: Dict,
        provided_data: Dict,
        document_type: KYBDocumentType
    ) -> Dict:
        """Validate extracted business data"""
        
        validation = {
            "required_fields_present": True,
            "business_name_match": False,
            "registration_number_match": False,
            "address_match": False,
            "directors_found": False,
            "missing_fields": [],
            "data_quality": "good"
        }
        
        # Check required fields
        required_fields = self._get_required_fields(document_type)
        
        for field in required_fields:
            if not extracted_data.get(field):
                validation["required_fields_present"] = False
                validation["missing_fields"].append(field)
        
        # Verify business name
        extracted_name = extracted_data.get("business_name", "").lower()
        provided_name = provided_data.get("business_name", "").lower()
        
        if extracted_name and provided_name:
            similarity = self._calculate_similarity(extracted_name, provided_name)
            validation["business_name_match"] = similarity >= 0.85
        
        # Verify registration number
        extracted_reg = extracted_data.get("registration_number", "")
        provided_reg = provided_data.get("registration_number", "")
        
        if extracted_reg and provided_reg:
            validation["registration_number_match"] = (
                extracted_reg.replace(" ", "").replace("-", "") ==
                provided_reg.replace(" ", "").replace("-", "")
            )
        
        # Check directors
        validation["directors_found"] = len(extracted_data.get("directors", [])) > 0
        
        # Assess data quality
        confidence = extracted_data.get("confidence", 0.0)
        if confidence >= 0.95:
            validation["data_quality"] = "excellent"
        elif confidence >= 0.85:
            validation["data_quality"] = "good"
        elif confidence >= 0.75:
            validation["data_quality"] = "acceptable"
        else:
            validation["data_quality"] = "poor"
        
        return validation
    
    def _calculate_risk_level(
        self,
        confidence_score: float,
        validation_results: Dict,
        directors: List[Dict],
        shareholders: List[Dict]
    ) -> RiskLevel:
        """Calculate risk level for business"""
        
        risk_score = 0
        
        # Low confidence increases risk
        if confidence_score < 0.75:
            risk_score += 3
        elif confidence_score < 0.85:
            risk_score += 1
        
        # Missing required fields
        if not validation_results.get("required_fields_present"):
            risk_score += 2
        
        # Business name mismatch
        if not validation_results.get("business_name_match"):
            risk_score += 2
        
        # No directors found (suspicious)
        if not validation_results.get("directors_found"):
            risk_score += 3
        
        # Poor data quality
        if validation_results.get("data_quality") == "poor":
            risk_score += 3
        
        # Complex ownership structure (potential shell company)
        if len(shareholders) > 10:
            risk_score += 1
        
        # No beneficial owners identified
        if len(shareholders) == 0 and len(directors) > 0:
            risk_score += 2
        
        # Determine risk level
        if risk_score >= 8:
            return RiskLevel.CRITICAL
        elif risk_score >= 5:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _determine_status(
        self,
        confidence_score: float,
        validation_results: Dict,
        risk_level: RiskLevel
    ) -> VerificationStatus:
        """Determine verification status"""
        
        # Critical risk = automatic rejection
        if risk_level == RiskLevel.CRITICAL:
            return VerificationStatus.REJECTED
        
        # High risk = requires manual review
        if risk_level == RiskLevel.HIGH:
            return VerificationStatus.REQUIRES_REVIEW
        
        # Low confidence = requires review
        if confidence_score < 0.85:
            return VerificationStatus.REQUIRES_REVIEW
        
        # Missing required fields = requires review
        if not validation_results.get("required_fields_present"):
            return VerificationStatus.REQUIRES_REVIEW
        
        # Business name mismatch = requires review
        if not validation_results.get("business_name_match"):
            return VerificationStatus.REQUIRES_REVIEW
        
        # All checks passed = verified
        return VerificationStatus.VERIFIED
    
    def _identify_issues(self, validation_results: Dict) -> List[str]:
        """Identify specific issues"""
        
        issues = []
        
        if validation_results.get("missing_fields"):
            issues.append(f"Missing required fields: {', '.join(validation_results['missing_fields'])}")
        
        if not validation_results.get("business_name_match"):
            issues.append("Business name mismatch between document and provided data")
        
        if not validation_results.get("registration_number_match"):
            issues.append("Registration number mismatch")
        
        if not validation_results.get("directors_found"):
            issues.append("No directors identified in document")
        
        if validation_results.get("data_quality") == "poor":
            issues.append("Poor document quality - may be illegible or damaged")
        
        return issues
    
    def _get_required_fields(self, document_type: KYBDocumentType) -> List[str]:
        """Get required fields for document type"""
        
        field_map = {
            KYBDocumentType.BUSINESS_REGISTRATION: [
                "business_name", "registration_number", "registration_date"
            ],
            KYBDocumentType.ARTICLES_OF_INCORPORATION: [
                "business_name", "registration_number", "directors"
            ],
            KYBDocumentType.MEMORANDUM_OF_ASSOCIATION: [
                "business_name", "shareholders"
            ],
            KYBDocumentType.TAX_CERTIFICATE: [
                "business_name", "registration_number"
            ],
            KYBDocumentType.BUSINESS_LICENSE: [
                "business_name", "license_number"
            ]
        }
        
        return field_map.get(document_type, ["business_name"])
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity"""
        
        if str1 == str2:
            return 1.0
        
        if not str1 or not str2:
            return 0.0
        
        # Simple token-based similarity
        tokens1 = set(str1.lower().split())
        tokens2 = set(str2.lower().split())
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0

# Initialize service
kyb_service = EnhancedKYBService()

# API endpoints
@app.post("/api/v1/kyb/verify-document", response_model=KYBVerificationResult)
async def verify_business_document(
    file: UploadFile = File(...),
    business_id: str = "biz123",
    document_type: KYBDocumentType = KYBDocumentType.BUSINESS_REGISTRATION,
    business_name: str = "",
    registration_number: str = "",
    business_address: str = ""
):
    """Verify business document with automated parsing"""
    
    # Save uploaded file
    temp_path = Path(f"/tmp/kyb_{business_id}_{file.filename}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Prepare provided data
    provided_data = {
        "business_name": business_name,
        "registration_number": registration_number,
        "business_address": business_address
    }
    
    # Verify document
    result = await kyb_service.verify_business_document(
        business_id,
        temp_path,
        document_type,
        provided_data
    )
    
    # Clean up
    temp_path.unlink()
    
    return result

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "enhanced-kyb",
        "version": "2.0.0",
        "deepseek_enabled": True,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8043)
