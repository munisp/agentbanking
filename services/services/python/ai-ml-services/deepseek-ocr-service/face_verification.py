"""
Face Matching and Liveness Detection Service
Complements DeepSeek-OCR for complete KYC verification
"""

import cv2
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from PIL import Image
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class LivenessStatus(Enum):
    """Liveness detection status"""
    LIVE = "live"
    SPOOF = "spoof"
    UNCERTAIN = "uncertain"

@dataclass
class FaceMatchResult:
    """Face matching result"""
    match_id: str
    is_match: bool
    similarity_score: float
    confidence: float
    face_detected_id: bool
    face_detected_selfie: bool
    timestamp: str

@dataclass
class LivenessResult:
    """Liveness detection result"""
    liveness_id: str
    status: str
    confidence: float
    checks_passed: Dict[str, bool]
    warnings: list
    timestamp: str

class FaceVerificationService:
    """
    Face Matching and Liveness Detection Service
    Uses computer vision techniques for KYC verification
    """
    
    def __init__(self):
        """Initialize face verification service"""
        self.face_cascade = None
        self.eye_cascade = None
        self.is_initialized = False
        
        logger.info("Initializing Face Verification Service")
    
    def initialize(self):
        """Initialize OpenCV cascades"""
        try:
            # Load Haar Cascade classifiers
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            
            self.is_initialized = True
            logger.info("Face verification service initialized")
            
        except Exception as e:
            logger.error(f"Error initializing face verification: {str(e)}")
            raise
    
    def match_faces(
        self,
        id_photo_path: str,
        selfie_path: str,
        user_id: str,
        match_id: Optional[str] = None
    ) -> FaceMatchResult:
        """
        Match face from ID photo with selfie
        
        Args:
            id_photo_path: Path to ID photo
            selfie_path: Path to selfie
            user_id: User ID for tracking
            match_id: Optional match ID
            
        Returns:
            FaceMatchResult with similarity score and match status
        """
        if not self.is_initialized:
            self.initialize()
        
        if match_id is None:
            match_id = f"MATCH_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        try:
            # Extract faces from both images
            id_face, id_detected = self._extract_face(id_photo_path)
            selfie_face, selfie_detected = self._extract_face(selfie_path)
            
            # Calculate similarity if both faces detected
            if id_detected and selfie_detected:
                similarity_score = self._calculate_similarity(id_face, selfie_face)
                confidence = self._calculate_match_confidence(similarity_score)
                is_match = similarity_score >= 0.70  # 70% threshold
            else:
                similarity_score = 0.0
                confidence = 0.0
                is_match = False
            
            result = FaceMatchResult(
                match_id=match_id,
                is_match=is_match,
                similarity_score=similarity_score,
                confidence=confidence,
                face_detected_id=id_detected,
                face_detected_selfie=selfie_detected,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(f"Face matching completed: {match_id} - Match: {is_match}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error matching faces: {str(e)}")
            raise
    
    def detect_liveness(
        self,
        selfie_path: str,
        user_id: str,
        liveness_id: Optional[str] = None
    ) -> LivenessResult:
        """
        Detect if selfie is from a live person (not a photo/video)
        
        Args:
            selfie_path: Path to selfie image
            user_id: User ID for tracking
            liveness_id: Optional liveness ID
            
        Returns:
            LivenessResult with liveness status and confidence
        """
        if not self.is_initialized:
            self.initialize()
        
        if liveness_id is None:
            liveness_id = f"LIVE_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        try:
            # Perform liveness checks
            checks = {
                'face_detected': False,
                'eyes_detected': False,
                'proper_lighting': False,
                'no_screen_glare': False,
                'proper_distance': False
            }
            
            warnings = []
            
            # Load image
            image = cv2.imread(selfie_path)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect face
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            if len(faces) > 0:
                checks['face_detected'] = True
                
                # Get largest face
                face = max(faces, key=lambda f: f[2] * f[3])
                x, y, w, h = face
                
                # Check face size (proper distance)
                face_area = w * h
                image_area = image.shape[0] * image.shape[1]
                face_ratio = face_area / image_area
                
                if 0.15 <= face_ratio <= 0.50:
                    checks['proper_distance'] = True
                else:
                    warnings.append("Face too close or too far from camera")
                
                # Detect eyes within face region
                roi_gray = gray[y:y+h, x:x+w]
                eyes = self.eye_cascade.detectMultiScale(roi_gray)
                
                if len(eyes) >= 2:
                    checks['eyes_detected'] = True
                else:
                    warnings.append("Both eyes not clearly visible")
                
                # Check lighting (brightness)
                brightness = np.mean(roi_gray)
                if 80 <= brightness <= 180:
                    checks['proper_lighting'] = True
                else:
                    warnings.append("Lighting too bright or too dark")
                
                # Check for screen glare (high intensity spots)
                _, thresh = cv2.threshold(roi_gray, 240, 255, cv2.THRESH_BINARY)
                glare_pixels = np.sum(thresh == 255)
                glare_ratio = glare_pixels / (w * h)
                
                if glare_ratio < 0.05:
                    checks['no_screen_glare'] = True
                else:
                    warnings.append("Possible screen glare detected")
            else:
                warnings.append("No face detected in image")
            
            # Calculate confidence and determine status
            passed_checks = sum(checks.values())
            total_checks = len(checks)
            confidence = passed_checks / total_checks
            
            if confidence >= 0.80:
                status = LivenessStatus.LIVE
            elif confidence >= 0.60:
                status = LivenessStatus.UNCERTAIN
            else:
                status = LivenessStatus.SPOOF
            
            result = LivenessResult(
                liveness_id=liveness_id,
                status=status.value,
                confidence=confidence,
                checks_passed=checks,
                warnings=warnings,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(f"Liveness detection completed: {liveness_id} - Status: {status.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error detecting liveness: {str(e)}")
            raise
    
    def _extract_face(self, image_path: str) -> Tuple[np.ndarray, bool]:
        """
        Extract face from image
        
        Args:
            image_path: Path to image
            
        Returns:
            Tuple of (face_array, detected)
        """
        try:
            image = cv2.imread(image_path)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            if len(faces) == 0:
                return np.array([]), False
            
            # Get largest face
            face = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = face
            
            # Extract and resize face
            face_img = gray[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (128, 128))
            
            return face_img, True
            
        except Exception as e:
            logger.error(f"Error extracting face: {str(e)}")
            return np.array([]), False
    
    def _calculate_similarity(
        self,
        face1: np.ndarray,
        face2: np.ndarray
    ) -> float:
        """
        Calculate similarity between two faces
        
        Args:
            face1: First face array
            face2: Second face array
            
        Returns:
            Similarity score (0-1)
        """
        try:
            # Normalize faces
            face1_norm = face1.astype(float) / 255.0
            face2_norm = face2.astype(float) / 255.0
            
            # Calculate structural similarity
            # Using simple correlation coefficient
            face1_flat = face1_norm.flatten()
            face2_flat = face2_norm.flatten()
            
            correlation = np.corrcoef(face1_flat, face2_flat)[0, 1]
            
            # Convert correlation to similarity score (0-1)
            similarity = (correlation + 1) / 2
            
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0
    
    def _calculate_match_confidence(self, similarity_score: float) -> float:
        """Calculate confidence in match result"""
        # Higher confidence for scores further from threshold
        threshold = 0.70
        distance_from_threshold = abs(similarity_score - threshold)
        
        # Confidence increases with distance from threshold
        confidence = 0.5 + (distance_from_threshold * 1.0)
        
        return max(0.0, min(1.0, confidence))
    
    def verify_complete_kyc(
        self,
        id_photo_path: str,
        selfie_path: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Complete KYC verification (face match + liveness)
        
        Args:
            id_photo_path: Path to ID photo
            selfie_path: Path to selfie
            user_id: User ID
            
        Returns:
            Complete verification result
        """
        try:
            # Face matching
            match_result = self.match_faces(id_photo_path, selfie_path, user_id)
            
            # Liveness detection
            liveness_result = self.detect_liveness(selfie_path, user_id)
            
            # Overall verification decision
            is_verified = (
                match_result.is_match and
                liveness_result.status == LivenessStatus.LIVE.value
            )
            
            overall_confidence = (
                match_result.confidence * 0.6 +
                liveness_result.confidence * 0.4
            )
            
            return {
                "success": True,
                "is_verified": is_verified,
                "overall_confidence": overall_confidence,
                "face_match": asdict(match_result),
                "liveness": asdict(liveness_result),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in complete KYC verification: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# API endpoint functions
async def match_faces_api(
    id_photo_path: str,
    selfie_path: str,
    user_id: str
) -> Dict[str, Any]:
    """API endpoint for face matching"""
    try:
        service = FaceVerificationService()
        result = service.match_faces(id_photo_path, selfie_path, user_id)
        
        return {
            "success": True,
            **asdict(result)
        }
        
    except Exception as e:
        logger.error(f"Error in match_faces_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def detect_liveness_api(
    selfie_path: str,
    user_id: str
) -> Dict[str, Any]:
    """API endpoint for liveness detection"""
    try:
        service = FaceVerificationService()
        result = service.detect_liveness(selfie_path, user_id)
        
        return {
            "success": True,
            **asdict(result)
        }
        
    except Exception as e:
        logger.error(f"Error in detect_liveness_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def verify_complete_kyc_api(
    id_photo_path: str,
    selfie_path: str,
    user_id: str
) -> Dict[str, Any]:
    """API endpoint for complete KYC verification"""
    try:
        service = FaceVerificationService()
        result = service.verify_complete_kyc(id_photo_path, selfie_path, user_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in verify_complete_kyc_api: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
