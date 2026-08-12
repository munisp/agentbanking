"""
KYC Integration Services
Integrate existing KYC services into onboarding flow

Services:
1. Face Verification Integration
2. PEP Screening Integration
3. Document Security Integration
4. Manual Review Integration

FAIL CLOSED: these integrations never fabricate a passing verification.
When the underlying KYC service is not configured/available, the user is
flagged for manual review and the call returns a non-success result so
onboarding is blocked - KYC state is only advanced on a real, positive
verification result.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logger = logging.getLogger(__name__)


class VerificationUnavailableError(RuntimeError):
    """Raised when an underlying KYC verification service is unavailable."""


def _load_service(module_name: str, class_name: str):
    """Best-effort import of a real KYC service class.

    Returns None when the service cannot be imported/instantiated; callers
    must treat that as verification-unavailable and fail closed.
    """
    import importlib

    module = importlib.import_module(module_name)
    service_class = getattr(module, class_name)
    return service_class()


class FaceVerificationIntegration:
    """
    Integrate face verification service into onboarding

    Connects to: services/kyc-enhanced/face-verification
    """
    
    def __init__(self, db_connection) -> None:
        self.db = db_connection
        self.face_service = None
    
    async def initialize(self) -> None:
        """Initialize face verification service.
        
        On failure the service stays None and every verification call fails
        closed (manual review) instead of returning a fabricated pass.
        """
        try:
            self.face_service = _load_service(
                "face_verification_service", "FaceVerificationService"
            )
            logger.info("Face verification service initialized")
        except Exception as e:
            logger.error(
                f"Failed to initialize face verification service; "
                f"face verification will fail closed (manual review): {e}"
            )
            self.face_service = None
    
    def _require_service(self):
        if self.face_service is None:
            raise VerificationUnavailableError(
                "Face verification service is not configured/available."
            )
        return self.face_service
    
    async def verify_user_face(
        self,
        user_id: str,
        selfie_path: str,
        id_photo_path: str
    ) -> Dict[str, Any]:
        """
        Verify user's face against ID photo
        
        Args:
            user_id: User ID
            selfie_path: Path to selfie image
            id_photo_path: Path to ID photo
            
        Returns:
            Verification result with KYC status update
        """
        try:
            service = self._require_service()
            
            with open(selfie_path, "rb") as f:
                selfie_image = f.read()
            with open(id_photo_path, "rb") as f:
                id_photo_image = f.read()
            
            # Call the real face verification service
            result = await service.verify_face_match(
                selfie_image, id_photo_image
            )
            
            verified = bool(getattr(result, "is_match", False))
            
            # Store result in database
            await self._store_face_verification_result(user_id, result.__dict__ if hasattr(result, "__dict__") else result)
            
            # Update KYC status
            if verified:
                await self._update_kyc_status(user_id, "face_verified")
                logger.info(f"Face verified for user {user_id}")
            else:
                await self._flag_for_manual_review(
                    user_id,
                    "face_verification_failed",
                    "Face verification failed"
                )
            
            return {
                "success": verified,
                "similarity": getattr(result, "similarity_score", None),
                "message": "Face verified successfully" if verified else "Face verification failed"
            }
        
        except Exception as e:
            # Fail closed: block onboarding and route to manual review.
            logger.error(f"Face verification error for user {user_id}: {e}")
            await self._flag_for_manual_review(
                user_id,
                "face_verification_unavailable",
                f"Face verification could not be completed: {e}"
            )
            return {
                "success": False,
                "requires_manual_review": True,
                "error": str(e)
            }
    
    async def verify_liveness(
        self,
        user_id: str,
        video_path: str
    ) -> Dict[str, Any]:
        """
        Verify liveness from video
        
        Args:
            user_id: User ID
            video_path: Path to liveness video
            
        Returns:
            Liveness verification result
        """
        try:
            from face_verification_service import LivenessCheckType
            
            service = self._require_service()
            
            with open(video_path, "rb") as f:
                video_data = f.read()
            
            result = await service.perform_liveness_check(
                LivenessCheckType.BLINK_DETECTION,
                video_frames=[video_data],
            )
            
            await self._store_liveness_result(user_id, result.__dict__ if hasattr(result, "__dict__") else result)
            
            is_live = bool(getattr(result, "is_live", False))
            if not is_live:
                await self._flag_for_manual_review(
                    user_id,
                    "liveness_check_failed",
                    "Liveness check failed"
                )
            
            return {
                "success": is_live,
                "confidence": getattr(result, "confidence", 0.0),
            }
        
        except Exception as e:
            # Fail closed: never report liveness as detected on error.
            logger.error(f"Liveness verification error: {e}")
            await self._flag_for_manual_review(
                user_id,
                "liveness_verification_unavailable",
                f"Liveness verification could not be completed: {e}"
            )
            return {
                "success": False,
                "requires_manual_review": True,
                "error": str(e)
            }
    
    async def _store_face_verification_result(self, user_id: str, result: Dict) -> None:
        """Store face verification result"""
        logger.info(f"Face verification result stored for user {user_id}")
    
    async def _store_liveness_result(self, user_id: str, result: Dict) -> None:
        """Store liveness result"""
        logger.info(f"Liveness result stored for user {user_id}")
    
    async def _update_kyc_status(self, user_id: str, status: str) -> None:
        """Update KYC status"""
        logger.info(f"KYC status updated to {status} for user {user_id}")
    
    async def _flag_for_manual_review(self, user_id: str, reason_code: str, reason: str) -> None:
        """Flag for manual review"""
        logger.warning(f"User {user_id} flagged for manual review: {reason}")


class PEPScreeningIntegration:
    """
    Integrate PEP screening service into onboarding

    Connects to: services/kyc-enhanced/pep-screening
    """
    
    def __init__(self, db_connection) -> None:
        self.db = db_connection
        self.pep_service = None
    
    async def initialize(self) -> None:
        """Initialize PEP screening service.
        
        On failure the service stays None and every screening call fails
        closed (manual review) instead of returning a fabricated clear
        result.
        """
        try:
            self.pep_service = _load_service(
                "pep_screening_service", "PEPScreeningService"
            )
            logger.info("PEP screening service initialized")
        except Exception as e:
            logger.error(
                f"Failed to initialize PEP screening service; "
                f"screening will fail closed (manual review): {e}"
            )
            self.pep_service = None
    
    async def screen_user(
        self,
        user_id: str,
        user_data: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Screen user for PEP and sanctions
        
        Args:
            user_id: User ID
            user_data: {name, dob, nationality, etc.}
            
        Returns:
            Screening result
        """
        try:
            if self.pep_service is None:
                raise VerificationUnavailableError(
                    "PEP screening service is not configured/available."
                )
            
            # Call the real PEP screening service (raises on unavailable)
            screening = await self.pep_service.screen_individual(
                full_name=user_data.get("name", ""),
                date_of_birth=user_data.get("dob"),
                nationality=user_data.get("nationality"),
            )
            
            result = {
                "pep_match": screening.is_pep,
                "sanctions_match": screening.is_sanctioned,
                "adverse_media_match": screening.has_adverse_media,
                "risk_score": screening.risk_score,
            }
            
            # Store result
            await self._store_pep_screening_result(user_id, result)
            
            # Determine action based on result
            if result['pep_match'] or result['sanctions_match']:
                # High risk - manual review required
                await self._flag_for_manual_review(
                    user_id,
                    "pep_or_sanctions_match",
                    "PEP or sanctions match detected",
                    priority="high"
                )
                
                return {
                    "success": True,
                    "requires_manual_review": True,
                    "risk_level": "high",
                    "pep_match": result['pep_match'],
                    "sanctions_match": result['sanctions_match']
                }
            
            elif result['risk_score'] > 70:
                # Medium risk - enhanced due diligence
                await self._flag_for_enhanced_due_diligence(user_id, result)
                
                return {
                    "success": True,
                    "requires_enhanced_due_diligence": True,
                    "risk_level": "medium",
                    "risk_score": result['risk_score']
                }
            
            else:
                # Low risk - approve
                await self._update_kyc_status(user_id, "pep_screening_passed")
                
                return {
                    "success": True,
                    "risk_level": "low",
                    "risk_score": result['risk_score'],
                    "message": "PEP screening passed"
                }
        
        except Exception as e:
            # Fail closed: an unscreened user is never auto-approved.
            logger.error(f"PEP screening error for user {user_id}: {e}")
            await self._flag_for_manual_review(
                user_id,
                "pep_screening_unavailable",
                f"PEP screening could not be completed: {e}",
                priority="high"
            )
            return {
                "success": False,
                "requires_manual_review": True,
                "risk_level": "unknown",
                "error": str(e)
            }
    
    async def setup_ongoing_monitoring(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Set up ongoing PEP monitoring (30-day rescreening)
        
        Args:
            user_id: User ID
            
        Returns:
            Setup result
        """
        try:
            # Schedule ongoing monitoring
            await self._schedule_ongoing_monitoring(user_id, interval_days=30)
            
            logger.info(f"Ongoing PEP monitoring set up for user {user_id}")
            
            return {
                "success": True,
                "monitoring_interval_days": 30,
                "message": "Ongoing monitoring activated"
            }
        
        except Exception as e:
            logger.error(f"Failed to setup ongoing monitoring: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_pep_screening_result(self, user_id: str, result: Dict) -> None:
        """Store PEP screening result"""
        logger.info(f"PEP screening result stored for user {user_id}")
    
    async def _flag_for_manual_review(
        self,
        user_id: str,
        reason_code: str,
        reason: str,
        priority: str = "medium"
    ) -> None:
        """Flag for manual review"""
        logger.warning(f"User {user_id} flagged for manual review ({priority}): {reason}")
    
    async def _flag_for_enhanced_due_diligence(self, user_id: str, result: Dict) -> None:
        """Flag for enhanced due diligence"""
        logger.info(f"User {user_id} flagged for enhanced due diligence")
    
    async def _update_kyc_status(self, user_id: str, status: str) -> None:
        """Update KYC status"""
        logger.info(f"KYC status updated to {status} for user {user_id}")
    
    async def _schedule_ongoing_monitoring(self, user_id: str, interval_days: int) -> None:
        """Schedule ongoing monitoring"""
        logger.info(f"Ongoing monitoring scheduled for user {user_id} (every {interval_days} days)")


class DocumentSecurityIntegration:
    """
    Integrate document security service into onboarding

    Connects to: services/kyc-enhanced/document-security
    """
    
    def __init__(self, db_connection) -> None:
        self.db = db_connection
        self.doc_service = None
    
    async def initialize(self) -> None:
        """Initialize document security service.
        
        On failure the service stays None and every verification call fails
        closed (manual review) instead of returning a fabricated authentic
        result.
        """
        try:
            self.doc_service = _load_service(
                "document_security_service", "DocumentSecurityService"
            )
            logger.info("Document security service initialized")
        except Exception as e:
            logger.error(
                f"Failed to initialize document security service; "
                f"document verification will fail closed (manual review): {e}"
            )
            self.doc_service = None
    
    async def verify_document_security(
        self,
        user_id: str,
        document_path: str,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Verify document security (forgery, tampering detection)
        
        Args:
            user_id: User ID
            document_path: Path to document image
            document_type: Type (passport, drivers_license, national_id, etc.)
            
        Returns:
            Security verification result
        """
        try:
            if self.doc_service is None:
                raise VerificationUnavailableError(
                    "Document security service is not configured/available."
                )
            
            # Call the real document security service
            result = await self.doc_service.verify_document(
                document_path, document_type
            )
            
            # Store result
            await self._store_document_security_result(user_id, document_type, result)
            
            # Update KYC status
            if result.get('authentic') and not result.get('forgery_detected', True):
                await self._update_kyc_status(user_id, f"{document_type}_verified")
                
                return {
                    "success": True,
                    "authentic": True,
                    "quality_score": result.get('quality_score'),
                    "confidence": result.get('confidence'),
                    "message": "Document verified successfully"
                }
            else:
                # Document failed security checks
                await self._flag_for_manual_review(
                    user_id,
                    "document_security_failed",
                    f"Document security verification failed: forgery={result.get('forgery_detected')}, tampering={result.get('tampering_detected')}"
                )
                
                return {
                    "success": False,
                    "authentic": False,
                    "forgery_detected": result.get('forgery_detected'),
                    "tampering_detected": result.get('tampering_detected'),
                    "message": "Document failed security verification"
                }
        
        except Exception as e:
            # Fail closed: an unverified document is never marked authentic.
            logger.error(f"Document security verification error: {e}")
            await self._flag_for_manual_review(
                user_id,
                "document_security_unavailable",
                f"Document security verification could not be completed: {e}"
            )
            return {
                "success": False,
                "requires_manual_review": True,
                "error": str(e)
            }
    
    async def _store_document_security_result(
        self,
        user_id: str,
        document_type: str,
        result: Dict
    ) -> None:
        """Store document security result"""
        logger.info(f"Document security result stored for user {user_id}, type {document_type}")
    
    async def _update_kyc_status(self, user_id: str, status: str) -> None:
        """Update KYC status"""
        logger.info(f"KYC status updated to {status} for user {user_id}")
    
    async def _flag_for_manual_review(self, user_id: str, reason_code: str, reason: str) -> None:
        """Flag for manual review"""
        logger.warning(f"User {user_id} flagged for manual review: {reason}")


class ManualReviewIntegration:
    """
    Integrate manual review workflow into onboarding

    Connects to: services/kyc-enhanced/manual-review
    """
    
    def __init__(self, db_connection) -> None:
        self.db = db_connection
        self.review_service = None
    
    async def initialize(self) -> None:
        """Initialize manual review service"""
        try:
            self.review_service = _load_service(
                "manual_review_service", "ManualReviewWorkflow"
            )
            logger.info("Manual review service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize manual review: {e}")
            self.review_service = None
    
    async def route_to_manual_review(
        self,
        user_id: str,
        reason_code: str,
        reason: str,
        priority: str = "medium",
        additional_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Route user to manual review queue
        
        Args:
            user_id: User ID
            reason_code: Reason code (pep_match, document_failed, etc.)
            reason: Human-readable reason
            priority: Priority (low, medium, high, urgent)
            additional_data: Additional context data
            
        Returns:
            Review case details
        """
        try:
            # Create review case
            case_id = f"REVIEW-{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            # Store in database
            await self._create_review_case(
                case_id, user_id, reason_code, reason, priority, additional_data
            )
            
            # Determine SLA based on priority
            sla_hours = self._get_sla_hours(priority)
            
            # Notify compliance team
            await self._notify_compliance_team(case_id, priority, reason)
            
            # Update user status
            await self._update_user_status(user_id, "pending_manual_review")
            
            logger.info(f"User {user_id} routed to manual review: {case_id}")
            
            return {
                "success": True,
                "case_id": case_id,
                "priority": priority,
                "sla_hours": sla_hours,
                "message": f"Routed to manual review (SLA: {sla_hours} hours)"
            }
        
        except Exception as e:
            logger.error(f"Failed to route to manual review: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_sla_hours(self, priority: str) -> int:
        """Get SLA hours based on priority"""
        sla_map = {
            "urgent": 4,
            "high": 24,
            "medium": 48,
            "low": 72
        }
        return sla_map.get(priority, 48)
    
    async def _create_review_case(
        self,
        case_id: str,
        user_id: str,
        reason_code: str,
        reason: str,
        priority: str,
        additional_data: Optional[Dict]
    ) -> None:
        """Create review case in database"""
        logger.info(f"Review case created: {case_id}")
    
    async def _notify_compliance_team(self, case_id: str, priority: str, reason: str) -> None:
        """Notify compliance team"""
        logger.info(f"Compliance team notified for case {case_id} ({priority})")
    
    async def _update_user_status(self, user_id: str, status: str) -> None:
        """Update user status"""
        logger.info(f"User {user_id} status updated to {status}")


# Example usage
async def example_usage() -> None:
    """Example usage of all integrations"""
    
    # Face Verification
    face_integration = FaceVerificationIntegration(db_connection=None)
    await face_integration.initialize()
    
    face_result = await face_integration.verify_user_face(
        user_id="user123",
        selfie_path="/path/to/selfie.jpg",
        id_photo_path="/path/to/id_photo.jpg"
    )
    print(f"Face verification: {face_result}")
    
    # PEP Screening
    pep_integration = PEPScreeningIntegration(db_connection=None)
    await pep_integration.initialize()
    
    pep_result = await pep_integration.screen_user(
        user_id="user123",
        user_data={
            "name": "John Doe",
            "dob": "1990-01-01",
            "nationality": "NG"
        }
    )
    print(f"\nPEP screening: {pep_result}")
    
    # Document Security
    doc_integration = DocumentSecurityIntegration(db_connection=None)
    await doc_integration.initialize()
    
    doc_result = await doc_integration.verify_document_security(
        user_id="user123",
        document_path="/path/to/passport.jpg",
        document_type="passport"
    )
    print(f"\nDocument security: {doc_result}")
    
    # Manual Review
    review_integration = ManualReviewIntegration(db_connection=None)
    await review_integration.initialize()
    
    review_result = await review_integration.route_to_manual_review(
        user_id="user123",
        reason_code="high_risk_country",
        reason="User from high-risk jurisdiction",
        priority="high"
    )
    print(f"\nManual review: {review_result}")


if __name__ == "__main__":
    asyncio.run(example_usage())
