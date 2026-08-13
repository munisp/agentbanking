"""
Face Verification Service with Liveness Detection
Enterprise-grade biometric verification for KYC

Features:
- Face matching (selfie vs ID photo)
- Liveness detection (prevent photo of photo attacks)
- Multi-provider support (AWS Rekognition, Azure Face API, Face++)
- Anti-spoofing detection
- Quality checks (lighting, blur, occlusion)

FAIL CLOSED: every provider client in this module calls the real upstream
API (AWS Rekognition via boto3, Azure Face API via HTTPS). When the required
credentials/SDK are not configured, the client raises
VerificationProviderUnavailableError instead of returning fabricated
"production" responses. Liveness checks have no server-side provider
integrated yet and therefore always fail loud rather than returning a
canned is_live=True verdict.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import aiohttp
from datetime import datetime


logger = logging.getLogger(__name__)


class VerificationProviderUnavailableError(RuntimeError):
    """Raised when no real face/liveness verification provider is configured.

    This error must never be swallowed and converted into a passing result;
    callers must treat it as verification-unavailable (e.g. manual review).
    """


class FaceVerificationProvider(Enum):
    """Face verification providers"""
    AWS_REKOGNITION = "aws_rekognition"
    AZURE_FACE_API = "azure_face_api"
    FACE_PLUS_PLUS = "face_plus_plus"


class LivenessCheckType(Enum):
    """Types of liveness checks"""
    BLINK_DETECTION = "blink"
    HEAD_MOVEMENT = "head_movement"
    SMILE_DETECTION = "smile"
    CHALLENGE_RESPONSE = "challenge_response"


@dataclass
class FaceQualityMetrics:
    """Face image quality metrics"""
    brightness: float  # 0-100
    sharpness: float  # 0-100
    face_size: int  # pixels
    face_confidence: float  # 0-1
    occlusion_score: float  # 0-1 (0 = no occlusion)
    pose_pitch: float  # degrees
    pose_yaw: float  # degrees
    pose_roll: float  # degrees
    
    def is_acceptable(self) -> bool:
        """Check if quality meets minimum standards"""
        return (
            30 <= self.brightness <= 90 and
            self.sharpness >= 50 and
            self.face_size >= 200 and
            self.face_confidence >= 0.95 and
            self.occlusion_score <= 0.3 and
            abs(self.pose_pitch) <= 15 and
            abs(self.pose_yaw) <= 15 and
            abs(self.pose_roll) <= 15
        )


@dataclass
class LivenessResult:
    """Liveness detection result"""
    is_live: bool
    confidence: float
    check_type: LivenessCheckType
    details: Dict[str, Any]
    timestamp: str


@dataclass
class FaceMatchResult:
    """Face matching result"""
    is_match: bool
    similarity_score: float  # 0-100
    confidence: float  # 0-1
    selfie_quality: FaceQualityMetrics
    id_photo_quality: FaceQualityMetrics
    provider: FaceVerificationProvider


class AWSRekognitionClient:
    """AWS Rekognition face verification client (real boto3 calls).

    Raises VerificationProviderUnavailableError when boto3 or credentials
    are not configured; never returns fabricated comparison results.
    """
    
    def __init__(self, region: str, access_key: str, secret_key: str) -> None:
        if not access_key or not secret_key:
            raise VerificationProviderUnavailableError(
                "AWS Rekognition credentials are not configured; face verification is unavailable."
            )
        try:
            import boto3
        except ImportError as exc:
            raise VerificationProviderUnavailableError(
                "boto3 is required for AWS Rekognition face verification but is not installed."
            ) from exc
        self.region = region
        self._client = boto3.client(
            "rekognition",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    
    async def compare_faces(
        self,
        source_image: bytes,
        target_image: bytes,
        similarity_threshold: float = 90.0
    ) -> Dict[str, Any]:
        """
        Compare two faces using AWS Rekognition
        
        Args:
            source_image: Source image bytes
            target_image: Target image bytes
            similarity_threshold: Minimum similarity (0-100)
            
        Returns:
            Comparison result with similarity score
        """
        logger.info("Comparing faces with AWS Rekognition")
        
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self._client.compare_faces(
                    SourceImage={"Bytes": source_image},
                    TargetImage={"Bytes": target_image},
                    SimilarityThreshold=similarity_threshold,
                ),
            )
        except Exception as exc:
            raise VerificationProviderUnavailableError(
                f"AWS Rekognition CompareFaces failed: {exc}"
            ) from exc
    
    async def detect_faces(self, image: bytes) -> Dict[str, Any]:
        """Detect faces and extract quality metrics"""
        logger.info("Detecting faces with AWS Rekognition")
        
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self._client.detect_faces(
                    Image={"Bytes": image},
                    Attributes=["ALL"],
                ),
            )
        except Exception as exc:
            raise VerificationProviderUnavailableError(
                f"AWS Rekognition DetectFaces failed: {exc}"
            ) from exc


class AzureFaceAPIClient:
    """Azure Face API client (real HTTPS calls).

    Raises VerificationProviderUnavailableError when the endpoint or
    subscription key is not configured, or when the upstream call fails.
    """
    
    def __init__(self, endpoint: str, subscription_key: str) -> None:
        if not endpoint or not subscription_key:
            raise VerificationProviderUnavailableError(
                "Azure Face API endpoint/subscription key are not configured; face verification is unavailable."
            )
        self.endpoint = endpoint.rstrip("/")
        self.subscription_key = subscription_key
    
    async def _post(self, path: str, params: Optional[Dict[str, Any]] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.endpoint}{path}"
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, params=params, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise VerificationProviderUnavailableError(
                        f"Azure Face API call to {path} failed with status {resp.status}: {body[:200]}"
                    )
                return await resp.json()
    
    async def detect(self, image_url: str) -> str:
        """Detect a face and return its faceId."""
        result = await self._post(
            "/face/v1.0/detect",
            params={"returnFaceId": "true"},
            payload={"url": image_url},
        )
        if not result:
            raise VerificationProviderUnavailableError(
                "Azure Face API detected no face in the provided image."
            )
        return result[0]["faceId"]
    
    async def verify_faces(
        self,
        face_id_1: str,
        face_id_2: str
    ) -> Dict[str, Any]:
        """Verify if two faces belong to same person (real API call)."""
        logger.info("Verifying faces with Azure Face API")
        return await self._post(
            "/face/v1.0/verify",
            payload={"faceId1": face_id_1, "faceId2": face_id_2},
        )
    
    async def detect_with_liveness(
        self,
        image: bytes,
        return_face_attributes: bool = True
    ) -> Dict[str, Any]:
        """Liveness detection is not available through this integration.
        
        Fail loud rather than returning a fabricated liveness score.
        """
        raise VerificationProviderUnavailableError(
            "Azure liveness detection is not integrated; refusing to return a fabricated liveness verdict."
        )


class LivenessDetector:
    """Liveness detection to prevent spoofing attacks.
    
    FAIL CLOSED: no server-side liveness provider is integrated. Every check
    raises VerificationProviderUnavailableError instead of returning a
    fabricated is_live=True verdict.
    """
    
    def __init__(self) -> None:
        self.min_confidence = 0.90
    
    def _unavailable(self, check: str) -> VerificationProviderUnavailableError:
        return VerificationProviderUnavailableError(
            f"Liveness check '{check}' is unavailable: no server-side liveness "
            "detection provider is configured. Route to manual review instead."
        )
    
    async def check_blink_detection(
        self,
        video_frames: List[bytes]
    ) -> LivenessResult:
        """Detect eye blinks in video frames"""
        raise self._unavailable(LivenessCheckType.BLINK_DETECTION.value)
    
    async def check_head_movement(
        self,
        video_frames: List[bytes]
    ) -> LivenessResult:
        """Detect head movement (left/right, up/down)"""
        raise self._unavailable(LivenessCheckType.HEAD_MOVEMENT.value)
    
    async def check_smile_detection(
        self,
        neutral_image: bytes,
        smiling_image: bytes
    ) -> LivenessResult:
        """Detect smile (challenge-response)"""
        raise self._unavailable(LivenessCheckType.SMILE_DETECTION.value)
    
    async def check_challenge_response(
        self,
        challenge: str,
        response_image: bytes
    ) -> LivenessResult:
        """Random challenge-response liveness check"""
        raise self._unavailable(LivenessCheckType.CHALLENGE_RESPONSE.value)


class FaceVerificationService:
    """
    Enterprise-grade face verification service
    
    Features:
    - Multi-provider support
    - Liveness detection
    - Quality checks
    - Anti-spoofing
    
    FAIL CLOSED: if the configured provider's credentials are missing, every
    verification entry point raises VerificationProviderUnavailableError.
    """
    
    def __init__(
        self,
        provider: FaceVerificationProvider = FaceVerificationProvider.AWS_REKOGNITION,
        aws_config: Optional[Dict[str, str]] = None,
        azure_config: Optional[Dict[str, str]] = None
    ) -> None:
        self.provider = provider
        self.liveness_detector = LivenessDetector()
        self.aws_client: Optional[AWSRekognitionClient] = None
        self.azure_client: Optional[AzureFaceAPIClient] = None
        
        # Initialize provider clients only when real credentials are supplied.
        if provider == FaceVerificationProvider.AWS_REKOGNITION and aws_config:
            self.aws_client = AWSRekognitionClient(
                region=aws_config.get("region", "us-east-1"),
                access_key=aws_config.get("access_key", ""),
                secret_key=aws_config.get("secret_key", "")
            )
        
        if provider == FaceVerificationProvider.AZURE_FACE_API and azure_config:
            self.azure_client = AzureFaceAPIClient(
                endpoint=azure_config.get("endpoint", ""),
                subscription_key=azure_config.get("subscription_key", "")
            )
    
    def _require_aws_client(self) -> AWSRekognitionClient:
        if not self.aws_client:
            raise VerificationProviderUnavailableError(
                "AWS Rekognition client is not configured; face verification is unavailable."
            )
        return self.aws_client
    
    async def verify_face_match(
        self,
        selfie_image: bytes,
        id_photo_image: bytes,
        similarity_threshold: float = 90.0
    ) -> FaceMatchResult:
        """
        Verify if selfie matches ID photo
        
        Args:
            selfie_image: Selfie image bytes
            id_photo_image: ID document photo bytes
            similarity_threshold: Minimum similarity score (0-100)
            
        Returns:
            Face match result
        """
        logger.info(f"Verifying face match using {self.provider.value}")
        
        if self.provider != FaceVerificationProvider.AWS_REKOGNITION:
            raise VerificationProviderUnavailableError(
                f"Provider {self.provider.value} is not configured for byte-image comparison; "
                "face verification is unavailable."
            )
        
        aws_client = self._require_aws_client()
        
        # Step 1: Check image quality
        selfie_quality = await self._check_image_quality(selfie_image)
        id_quality = await self._check_image_quality(id_photo_image)
        
        if not selfie_quality.is_acceptable():
            logger.warning(f"Selfie quality unacceptable: {selfie_quality}")
            return FaceMatchResult(
                is_match=False,
                similarity_score=0.0,
                confidence=0.0,
                selfie_quality=selfie_quality,
                id_photo_quality=id_quality,
                provider=self.provider
            )
        
        if not id_quality.is_acceptable():
            logger.warning(f"ID photo quality unacceptable: {id_quality}")
            return FaceMatchResult(
                is_match=False,
                similarity_score=0.0,
                confidence=0.0,
                selfie_quality=selfie_quality,
                id_photo_quality=id_quality,
                provider=self.provider
            )
        
        # Step 2: Compare faces
        result = await aws_client.compare_faces(
            selfie_image,
            id_photo_image,
            similarity_threshold
        )
        
        if result.get("FaceMatches"):
            match = result["FaceMatches"][0]
            similarity = match["Similarity"]
            confidence = match["Face"]["Confidence"] / 100.0
            
            return FaceMatchResult(
                is_match=similarity >= similarity_threshold,
                similarity_score=similarity,
                confidence=confidence,
                selfie_quality=selfie_quality,
                id_photo_quality=id_quality,
                provider=self.provider
            )
        
        # No match found
        return FaceMatchResult(
            is_match=False,
            similarity_score=0.0,
            confidence=0.0,
            selfie_quality=selfie_quality,
            id_photo_quality=id_quality,
            provider=self.provider
        )
    
    async def perform_liveness_check(
        self,
        check_type: LivenessCheckType,
        **kwargs
    ) -> LivenessResult:
        """
        Perform liveness detection.
        
        FAIL CLOSED: raises VerificationProviderUnavailableError because no
        server-side liveness provider is integrated.
        """
        logger.info(f"Performing liveness check: {check_type.value}")
        
        if check_type == LivenessCheckType.BLINK_DETECTION:
            return await self.liveness_detector.check_blink_detection(
                kwargs.get("video_frames", [])
            )
        
        elif check_type == LivenessCheckType.HEAD_MOVEMENT:
            return await self.liveness_detector.check_head_movement(
                kwargs.get("video_frames", [])
            )
        
        elif check_type == LivenessCheckType.SMILE_DETECTION:
            return await self.liveness_detector.check_smile_detection(
                kwargs.get("neutral_image"),
                kwargs.get("smiling_image")
            )
        
        elif check_type == LivenessCheckType.CHALLENGE_RESPONSE:
            return await self.liveness_detector.check_challenge_response(
                kwargs.get("challenge"),
                kwargs.get("response_image")
            )
        
        raise ValueError(f"Unsupported liveness check type: {check_type}")
    
    async def comprehensive_verification(
        self,
        selfie_image: bytes,
        id_photo_image: bytes,
        liveness_video_frames: List[bytes],
        similarity_threshold: float = 90.0
    ) -> Dict[str, Any]:
        """
        Comprehensive verification with face match + liveness
        
        Args:
            selfie_image: Selfie image
            id_photo_image: ID photo
            liveness_video_frames: Video frames for liveness check
            similarity_threshold: Minimum similarity
            
        Returns:
            Complete verification result
            
        Raises:
            VerificationProviderUnavailableError: when no real provider is
                configured. Callers must treat this as verification
                unavailable (e.g. manual review), never as a pass.
        """
        logger.info("Starting comprehensive face verification")
        
        # Step 1: Face matching (raises when provider unavailable)
        face_match = await self.verify_face_match(
            selfie_image,
            id_photo_image,
            similarity_threshold
        )
        
        if not face_match.is_match:
            return {
                "verified": False,
                "reason": "Face does not match ID photo",
                "face_match": {
                    "is_match": False,
                    "similarity_score": face_match.similarity_score,
                    "confidence": face_match.confidence
                },
                "liveness": None
            }
        
        # Step 2: Liveness detection (blink + head movement).
        # Raises VerificationProviderUnavailableError when no liveness
        # provider is configured - verification can never pass without it.
        liveness_blink = await self.perform_liveness_check(
            LivenessCheckType.BLINK_DETECTION,
            video_frames=liveness_video_frames
        )
        
        liveness_movement = await self.perform_liveness_check(
            LivenessCheckType.HEAD_MOVEMENT,
            video_frames=liveness_video_frames
        )
        
        # Both liveness checks must pass
        liveness_passed = (
            liveness_blink.is_live and
            liveness_movement.is_live and
            liveness_blink.confidence >= 0.90 and
            liveness_movement.confidence >= 0.90
        )
        
        if not liveness_passed:
            return {
                "verified": False,
                "reason": "Liveness check failed",
                "face_match": {
                    "is_match": True,
                    "similarity_score": face_match.similarity_score,
                    "confidence": face_match.confidence
                },
                "liveness": {
                    "passed": False,
                    "blink_check": {
                        "passed": liveness_blink.is_live,
                        "confidence": liveness_blink.confidence
                    },
                    "movement_check": {
                        "passed": liveness_movement.is_live,
                        "confidence": liveness_movement.confidence
                    }
                }
            }
        
        # All checks passed
        return {
            "verified": True,
            "reason": "Face match and liveness verified",
            "face_match": {
                "is_match": True,
                "similarity_score": face_match.similarity_score,
                "confidence": face_match.confidence,
                "provider": face_match.provider.value
            },
            "liveness": {
                "passed": True,
                "blink_check": {
                    "passed": True,
                    "confidence": liveness_blink.confidence,
                    "details": liveness_blink.details
                },
                "movement_check": {
                    "passed": True,
                    "confidence": liveness_movement.confidence,
                    "details": liveness_movement.details
                }
            },
            "overall_confidence": min(
                face_match.confidence,
                liveness_blink.confidence,
                liveness_movement.confidence
            ),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _check_image_quality(self, image: bytes) -> FaceQualityMetrics:
        """Check image quality metrics using the configured provider.
        
        Raises VerificationProviderUnavailableError when no provider client
        is configured; never returns fabricated "acceptable" metrics.
        """
        
        if self.provider == FaceVerificationProvider.AWS_REKOGNITION:
            aws_client = self._require_aws_client()
            result = await aws_client.detect_faces(image)
            
            if result.get("FaceDetails"):
                face = result["FaceDetails"][0]
                quality = face.get("Quality", {})
                pose = face.get("Pose", {})
                bbox = face.get("BoundingBox", {})
                
                # Calculate face size from bounding box
                face_size = int(bbox.get("Width", 0) * bbox.get("Height", 0) * 1000)
                
                return FaceQualityMetrics(
                    brightness=quality.get("Brightness", 50.0),
                    sharpness=quality.get("Sharpness", 50.0),
                    face_size=face_size,
                    face_confidence=face.get("Confidence", 0.0) / 100.0,
                    occlusion_score=0.0,  # AWS doesn't provide this directly
                    pose_pitch=pose.get("Pitch", 0.0),
                    pose_yaw=pose.get("Yaw", 0.0),
                    pose_roll=pose.get("Roll", 0.0)
                )
            
            raise VerificationProviderUnavailableError(
                "No face detected in image by AWS Rekognition."
            )
        
        raise VerificationProviderUnavailableError(
            f"Image quality check is unavailable for provider {self.provider.value}."
        )


# Example usage
async def example_usage() -> None:
    """Example usage of face verification service.
    
    Requires real AWS Rekognition credentials; raises
    VerificationProviderUnavailableError otherwise (fail closed).
    """
    
    # Initialize service
    service = FaceVerificationService(
        provider=FaceVerificationProvider.AWS_REKOGNITION,
        aws_config={
            "region": "us-east-1",
            "access_key": "your-access-key",
            "secret_key": "your-secret-key"
        }
    )
    
    # Load images (in production, these would be actual image bytes)
    selfie_image = b"selfie_image_bytes"
    id_photo_image = b"id_photo_bytes"
    video_frames = [b"frame1", b"frame2", b"frame3"]
    
    try:
        # Perform comprehensive verification
        result = await service.comprehensive_verification(
            selfie_image=selfie_image,
            id_photo_image=id_photo_image,
            liveness_video_frames=video_frames,
            similarity_threshold=90.0
        )
    except VerificationProviderUnavailableError as exc:
        print(f"Face verification unavailable (fail closed): {exc}")
        return
    
    if result["verified"]:
        print("Face verification passed!")
        print(f"Similarity: {result['face_match']['similarity_score']:.1f}%")
        print(f"Confidence: {result['overall_confidence']:.2f}")
    else:
        print(f"Face verification failed: {result['reason']}")


if __name__ == "__main__":
    asyncio.run(example_usage())
