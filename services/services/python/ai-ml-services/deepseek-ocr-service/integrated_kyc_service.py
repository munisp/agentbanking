"""
Integrated KYC Verification Service
Combines DeepSeek-OCR document verification with face matching and liveness detection
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from .deepseek_ocr_verifier import (
    DeepSeekOCRVerifier,
    DocumentType,
    VerificationStatus
)
from .face_verification import (
    FaceVerificationService,
    LivenessStatus
)

logger = logging.getLogger(__name__)

class KYCTier(Enum):
    """KYC verification tiers"""
    TIER_1 = "tier_1"  # Basic: Email + Phone
    TIER_2 = "tier_2"  # Standard: + ID Document
    TIER_3 = "tier_3"  # Enhanced: + Selfie + Liveness

@dataclass
class KYCLimits:
    """Transaction limits for KYC tiers"""
    tier: str
    daily_limit_ngn: float
    monthly_limit_ngn: float
    single_transaction_limit_ngn: float
    features: List[str]

@dataclass
class IntegratedKYCResult:
    """Complete KYC verification result"""
    kyc_id: str
    user_id: str
    current_tier: str
    target_tier: str
    status: str
    overall_confidence: float
    document_verification: Optional[Dict[str, Any]]
    face_match: Optional[Dict[str, Any]]
    liveness_detection: Optional[Dict[str, Any]]
    issues: List[str]
    warnings: List[str]
    next_steps: List[str]
    limits: Dict[str, Any]
    timestamp: str
    processing_time_ms: float

class IntegratedKYCService:
    """
    Integrated KYC Verification Service
    Orchestrates document verification, face matching, and liveness detection
    """
    
    # KYC tier limits
    TIER_LIMITS = {
        KYCTier.TIER_1: KYCLimits(
            tier="tier_1",
            daily_limit_ngn=50000,
            monthly_limit_ngn=200000,
            single_transaction_limit_ngn=20000,
            features=["basic_transfers", "wallet"]
        ),
        KYCTier.TIER_2: KYCLimits(
            tier="tier_2",
            daily_limit_ngn=500000,
            monthly_limit_ngn=2000000,
            single_transaction_limit_ngn=200000,
            features=["basic_transfers", "wallet", "international_transfers", "cards"]
        ),
        KYCTier.TIER_3: KYCLimits(
            tier="tier_3",
            daily_limit_ngn=5000000,
            monthly_limit_ngn=20000000,
            single_transaction_limit_ngn=2000000,
            features=["basic_transfers", "wallet", "international_transfers", "cards", "savings", "investments", "business_features"]
        )
    }
    
    def __init__(self):
        """Initialize integrated KYC service"""
        self.ocr_verifier = DeepSeekOCRVerifier()
        self.face_service = FaceVerificationService()
        
        logger.info("Initialized Integrated KYC Service")
    
    def verify_tier_2(
        self,
        user_id: str,
        id_document_path: str,
        document_type: DocumentType
    ) -> IntegratedKYCResult:
        """
        Verify user for Tier 2 (Standard KYC)
        Requires ID document verification
        
        Args:
            user_id: User ID
            id_document_path: Path to ID document image
            document_type: Type of document
            
        Returns:
            IntegratedKYCResult with verification status
        """
        start_time = datetime.utcnow()
        kyc_id = f"KYC_{user_id}_{int(start_time.timestamp())}"
        
        issues = []
        warnings = []
        next_steps = []
        
        try:
            # Verify document with DeepSeek-OCR
            doc_result = self.ocr_verifier.verify_document(
                image_path=id_document_path,
                document_type=document_type,
                user_id=user_id
            )
            
            # Check document verification status
            if doc_result.status == VerificationStatus.REJECTED.value:
                issues.extend(doc_result.issues)
                status = "rejected"
                overall_confidence = doc_result.confidence
                next_steps.append("Resubmit clear document photo")
                
            elif doc_result.status == VerificationStatus.MANUAL_REVIEW.value:
                warnings.extend(doc_result.warnings)
                status = "manual_review"
                overall_confidence = doc_result.confidence
                next_steps.append("Document under manual review (1-24 hours)")
                
            else:  # VERIFIED
                status = "verified"
                overall_confidence = doc_result.confidence
                next_steps.append("Tier 2 verification complete")
                next_steps.append("Upgrade to Tier 3 for higher limits")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Get tier limits
            limits = asdict(self.TIER_LIMITS[KYCTier.TIER_2])
            
            result = IntegratedKYCResult(
                kyc_id=kyc_id,
                user_id=user_id,
                current_tier="tier_1",
                target_tier="tier_2",
                status=status,
                overall_confidence=overall_confidence,
                document_verification=asdict(doc_result),
                face_match=None,
                liveness_detection=None,
                issues=issues,
                warnings=warnings,
                next_steps=next_steps,
                limits=limits,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=processing_time
            )
            
            logger.info(f"Tier 2 verification completed: {kyc_id} - {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Tier 2 verification: {str(e)}")
            raise
    
    def verify_tier_3(
        self,
        user_id: str,
        id_document_path: str,
        document_type: DocumentType,
        selfie_path: str
    ) -> IntegratedKYCResult:
        """
        Verify user for Tier 3 (Enhanced KYC)
        Requires ID document + selfie + liveness detection
        
        Args:
            user_id: User ID
            id_document_path: Path to ID document image
            document_type: Type of document
            selfie_path: Path to selfie image
            
        Returns:
            IntegratedKYCResult with complete verification status
        """
        start_time = datetime.utcnow()
        kyc_id = f"KYC_{user_id}_{int(start_time.timestamp())}"
        
        issues = []
        warnings = []
        next_steps = []
        
        try:
            # Step 1: Verify document with DeepSeek-OCR
            doc_result = self.ocr_verifier.verify_document(
                image_path=id_document_path,
                document_type=document_type,
                user_id=user_id
            )
            
            # Step 2: Match face from ID with selfie
            face_result = self.face_service.match_faces(
                id_photo_path=id_document_path,
                selfie_path=selfie_path,
                user_id=user_id
            )
            
            # Step 3: Detect liveness from selfie
            liveness_result = self.face_service.detect_liveness(
                selfie_path=selfie_path,
                user_id=user_id
            )
            
            # Aggregate results
            doc_verified = doc_result.status == VerificationStatus.VERIFIED.value
            face_matched = face_result.is_match
            liveness_passed = liveness_result.status == LivenessStatus.LIVE.value
            
            # Collect issues and warnings
            if not doc_verified:
                issues.extend(doc_result.issues)
                warnings.extend(doc_result.warnings)
            
            if not face_matched:
                issues.append("Face from ID does not match selfie")
            
            if not liveness_passed:
                if liveness_result.status == LivenessStatus.SPOOF.value:
                    issues.append("Liveness check failed - possible spoof detected")
                else:
                    warnings.append("Liveness check uncertain")
                warnings.extend(liveness_result.warnings)
            
            # Determine overall status
            if doc_verified and face_matched and liveness_passed:
                status = "verified"
                next_steps.append("Tier 3 verification complete")
                next_steps.append("All features unlocked")
            elif len(issues) > 0:
                status = "rejected"
                next_steps.append("Please address the issues and resubmit")
            else:
                status = "manual_review"
                next_steps.append("Verification under manual review (1-24 hours)")
            
            # Calculate overall confidence
            overall_confidence = (
                doc_result.confidence * 0.5 +
                face_result.confidence * 0.3 +
                liveness_result.confidence * 0.2
            )
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Get tier limits
            limits = asdict(self.TIER_LIMITS[KYCTier.TIER_3])
            
            result = IntegratedKYCResult(
                kyc_id=kyc_id,
                user_id=user_id,
                current_tier="tier_2",
                target_tier="tier_3",
                status=status,
                overall_confidence=overall_confidence,
                document_verification=asdict(doc_result),
                face_match=asdict(face_result),
                liveness_detection=asdict(liveness_result),
                issues=issues,
                warnings=warnings,
                next_steps=next_steps,
                limits=limits,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=processing_time
            )
            
            logger.info(f"Tier 3 verification completed: {kyc_id} - {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Tier 3 verification: {str(e)}")
            raise
    
    def get_tier_info(self, tier: KYCTier) -> Dict[str, Any]:
        """Get information about a KYC tier"""
        limits = self.TIER_LIMITS[tier]
        return asdict(limits)
    
    def get_all_tiers_info(self) -> List[Dict[str, Any]]:
        """Get information about all KYC tiers"""
        return [asdict(limits) for limits in self.TIER_LIMITS.values()]


# API endpoint functions
async def verify_kyc_tier_2_api(
    user_id: str,
    id_document_path: str,
    document_type: str
) -> Dict[str, Any]:
    """API endpoint for Tier 2 KYC verification"""
    try:
        service = IntegratedKYCService()
        
        # Convert string to DocumentType enum
        doc_type = DocumentType(document_type.lower())
        
        result = service.verify_tier_2(user_id, id_document_path, doc_type)
        
        return {
            "success": True,
            **asdict(result)
        }
        
    except Exception as e:
        logger.error(f"Error in verify_kyc_tier_2_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def verify_kyc_tier_3_api(
    user_id: str,
    id_document_path: str,
    document_type: str,
    selfie_path: str
) -> Dict[str, Any]:
    """API endpoint for Tier 3 KYC verification"""
    try:
        service = IntegratedKYCService()
        
        # Convert string to DocumentType enum
        doc_type = DocumentType(document_type.lower())
        
        result = service.verify_tier_3(
            user_id,
            id_document_path,
            doc_type,
            selfie_path
        )
        
        return {
            "success": True,
            **asdict(result)
        }
        
    except Exception as e:
        logger.error(f"Error in verify_kyc_tier_3_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_tier_info_api(tier: str) -> Dict[str, Any]:
    """API endpoint to get tier information"""
    try:
        service = IntegratedKYCService()
        
        tier_enum = KYCTier(tier.lower())
        info = service.get_tier_info(tier_enum)
        
        return {
            "success": True,
            "tier_info": info
        }
        
    except Exception as e:
        logger.error(f"Error in get_tier_info_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_all_tiers_info_api() -> Dict[str, Any]:
    """API endpoint to get all tiers information"""
    try:
        service = IntegratedKYCService()
        tiers = service.get_all_tiers_info()
        
        return {
            "success": True,
            "tiers": tiers
        }
        
    except Exception as e:
        logger.error(f"Error in get_all_tiers_info_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
