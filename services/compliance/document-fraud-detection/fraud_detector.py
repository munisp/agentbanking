"""
Document Fraud Detection Service
Uses DeepSeek OCR + image forensics to detect fraudulent documents
"""

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Optional
from enum import Enum
from pathlib import Path
from datetime import datetime
import logging
from PIL import Image
import numpy as np
import sys

# Add document processing path
sys.path.append(str(Path(__file__).parent.parent.parent / "document-processing/docling-service"))
from integrated_processor import IntegratedDocumentProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Fraud Detection", version="1.0.0")

class FraudRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FraudIndicator(str, Enum):
    TAMPERING = "tampering"
    FORGERY = "forgery"
    DUPLICATE = "duplicate"
    POOR_QUALITY = "poor_quality"
    INCONSISTENT_DATA = "inconsistent_data"
    SUSPICIOUS_PATTERNS = "suspicious_patterns"

class FraudDetectionResult(BaseModel):
    document_id: str
    fraud_risk_level: FraudRiskLevel
    fraud_score: float  # 0-100
    indicators: List[FraudIndicator]
    analysis: Dict
    recommendations: List[str]
    timestamp: str

class DocumentFraudDetector:
    """Detect fraudulent documents using ML and image forensics"""
    
    def __init__(self):
        # Initialize document processor
        self.doc_processor = IntegratedDocumentProcessor(
            use_deepseek=True,
            use_gpu=True
        )
        
        logger.info("Document Fraud Detector initialized")
    
    async def detect_fraud(
        self,
        document_path: Path,
        document_type: str
    ) -> FraudDetectionResult:
        """
        Detect fraud in document
        
        Args:
            document_path: Path to document
            document_type: Type of document
        
        Returns:
            FraudDetectionResult
        """
        document_id = f"doc_{datetime.utcnow().timestamp()}"
        
        try:
            # Step 1: Process document with DeepSeek OCR
            doc_result = await self.doc_processor.process_document(
                document_path,
                document_type=document_type,
                extract_entities=True,
                extract_tables=False
            )
            
            # Step 2: Analyze image quality and forensics
            image_analysis = self._analyze_image_forensics(document_path)
            
            # Step 3: Check for tampering indicators
            tampering_check = self._check_tampering(image_analysis)
            
            # Step 4: Validate data consistency
            consistency_check = self._check_data_consistency(doc_result)
            
            # Step 5: Check for duplicate/known fraudulent documents
            duplicate_check = self._check_duplicates(document_path)
            
            # Step 6: Calculate fraud score
            fraud_score = self._calculate_fraud_score(
                doc_result,
                image_analysis,
                tampering_check,
                consistency_check,
                duplicate_check
            )
            
            # Step 7: Identify fraud indicators
            indicators = self._identify_fraud_indicators(
                fraud_score,
                tampering_check,
                consistency_check,
                duplicate_check,
                doc_result
            )
            
            # Step 8: Determine risk level
            risk_level = self._determine_risk_level(fraud_score, indicators)
            
            # Step 9: Generate recommendations
            recommendations = self._generate_recommendations(risk_level, indicators)
            
            # Compile analysis
            analysis = {
                "ocr_confidence": doc_result.get("confidence", 0.0),
                "image_quality": image_analysis.get("quality_score", 0.0),
                "tampering_detected": tampering_check.get("tampering_detected", False),
                "data_consistent": consistency_check.get("consistent", True),
                "duplicate_found": duplicate_check.get("is_duplicate", False),
                "entity_count": len(doc_result.get("entities", [])),
                "text_length": len(doc_result.get("combined_text", ""))
            }
            
            result = FraudDetectionResult(
                document_id=document_id,
                fraud_risk_level=risk_level,
                fraud_score=fraud_score,
                indicators=indicators,
                analysis=analysis,
                recommendations=recommendations,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(
                f"Fraud detection complete: {document_id}, "
                f"risk: {risk_level}, score: {fraud_score:.1f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Fraud detection error: {e}")
            raise
    
    def _analyze_image_forensics(self, image_path: Path) -> Dict:
        """Analyze image for forensic indicators"""
        
        try:
            image = Image.open(image_path)
            img_array = np.array(image)
            
            analysis = {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "format": image.format,
                "quality_score": 0.0,
                "resolution_adequate": True,
                "color_consistency": True,
                "compression_artifacts": False
            }
            
            # Check resolution (minimum 300 DPI equivalent)
            min_dimension = min(image.width, image.height)
            analysis["resolution_adequate"] = min_dimension >= 800
            
            # Calculate quality score
            quality_score = 100.0
            
            if not analysis["resolution_adequate"]:
                quality_score -= 30
            
            if image.mode not in ["RGB", "L"]:
                quality_score -= 10
            
            # Check for extreme compression
            if image.format in ["JPEG", "JPG"]:
                # Simplified check - in production, use proper JPEG quality estimation
                if min_dimension < 500:
                    analysis["compression_artifacts"] = True
                    quality_score -= 20
            
            # Check color consistency (simplified)
            if image.mode == "RGB":
                # Calculate color variance
                variance = np.var(img_array)
                if variance < 100:  # Too uniform (suspicious)
                    analysis["color_consistency"] = False
                    quality_score -= 15
            
            analysis["quality_score"] = max(0, quality_score)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Image forensics error: {e}")
            return {
                "quality_score": 50.0,
                "resolution_adequate": False,
                "color_consistency": True,
                "compression_artifacts": True
            }
    
    def _check_tampering(self, image_analysis: Dict) -> Dict:
        """Check for tampering indicators"""
        
        tampering = {
            "tampering_detected": False,
            "tampering_score": 0.0,
            "indicators": []
        }
        
        score = 0.0
        
        # Low quality suggests manipulation
        if image_analysis.get("quality_score", 100) < 50:
            score += 30
            tampering["indicators"].append("low_quality")
        
        # Poor resolution
        if not image_analysis.get("resolution_adequate"):
            score += 20
            tampering["indicators"].append("low_resolution")
        
        # Color inconsistency
        if not image_analysis.get("color_consistency"):
            score += 25
            tampering["indicators"].append("color_inconsistency")
        
        # Compression artifacts
        if image_analysis.get("compression_artifacts"):
            score += 15
            tampering["indicators"].append("compression_artifacts")
        
        tampering["tampering_score"] = score
        tampering["tampering_detected"] = score >= 40
        
        return tampering
    
    def _check_data_consistency(self, doc_result: Dict) -> Dict:
        """Check for data consistency issues"""
        
        consistency = {
            "consistent": True,
            "issues": []
        }
        
        # Check if OCR confidence is suspiciously low
        confidence = doc_result.get("confidence", 0.0)
        if confidence < 0.70:
            consistency["consistent"] = False
            consistency["issues"].append("low_ocr_confidence")
        
        # Check for missing critical entities
        entities = doc_result.get("entities", [])
        if len(entities) < 2:
            consistency["consistent"] = False
            consistency["issues"].append("insufficient_data")
        
        # Check text length (too short = suspicious)
        text_length = len(doc_result.get("combined_text", ""))
        if text_length < 50:
            consistency["consistent"] = False
            consistency["issues"].append("insufficient_text")
        
        return consistency
    
    def _check_duplicates(self, document_path: Path) -> Dict:
        """Check for duplicate documents (simplified)"""
        
        # In production, use perceptual hashing (pHash) and database lookup
        # For now, return no duplicates
        
        return {
            "is_duplicate": False,
            "similarity_score": 0.0,
            "matched_documents": []
        }
    
    def _calculate_fraud_score(
        self,
        doc_result: Dict,
        image_analysis: Dict,
        tampering_check: Dict,
        consistency_check: Dict,
        duplicate_check: Dict
    ) -> float:
        """Calculate overall fraud score (0-100)"""
        
        score = 0.0
        
        # Tampering contributes up to 40 points
        score += tampering_check.get("tampering_score", 0.0) * 0.4
        
        # Low OCR confidence contributes up to 20 points
        ocr_confidence = doc_result.get("confidence", 1.0)
        score += (1.0 - ocr_confidence) * 20
        
        # Data inconsistency contributes up to 20 points
        if not consistency_check.get("consistent"):
            score += 20
        
        # Duplicate found contributes up to 20 points
        if duplicate_check.get("is_duplicate"):
            score += 20
        
        # Poor image quality contributes up to 10 points
        quality_score = image_analysis.get("quality_score", 100)
        score += (100 - quality_score) * 0.1
        
        return min(100.0, score)
    
    def _identify_fraud_indicators(
        self,
        fraud_score: float,
        tampering_check: Dict,
        consistency_check: Dict,
        duplicate_check: Dict,
        doc_result: Dict
    ) -> List[FraudIndicator]:
        """Identify specific fraud indicators"""
        
        indicators = []
        
        # Tampering detected
        if tampering_check.get("tampering_detected"):
            indicators.append(FraudIndicator.TAMPERING)
        
        # Duplicate document
        if duplicate_check.get("is_duplicate"):
            indicators.append(FraudIndicator.DUPLICATE)
        
        # Data inconsistency
        if not consistency_check.get("consistent"):
            indicators.append(FraudIndicator.INCONSISTENT_DATA)
        
        # Poor quality
        if fraud_score >= 30 and FraudIndicator.TAMPERING not in indicators:
            indicators.append(FraudIndicator.POOR_QUALITY)
        
        # Suspicious patterns (high fraud score without specific indicators)
        if fraud_score >= 50 and len(indicators) == 0:
            indicators.append(FraudIndicator.SUSPICIOUS_PATTERNS)
        
        # Potential forgery (combination of indicators)
        if (FraudIndicator.TAMPERING in indicators and 
            FraudIndicator.INCONSISTENT_DATA in indicators):
            indicators.append(FraudIndicator.FORGERY)
        
        return indicators
    
    def _determine_risk_level(
        self,
        fraud_score: float,
        indicators: List[FraudIndicator]
    ) -> FraudRiskLevel:
        """Determine fraud risk level"""
        
        # Critical risk if forgery detected
        if FraudIndicator.FORGERY in indicators:
            return FraudRiskLevel.CRITICAL
        
        # Risk based on fraud score
        if fraud_score >= 70:
            return FraudRiskLevel.CRITICAL
        elif fraud_score >= 50:
            return FraudRiskLevel.HIGH
        elif fraud_score >= 30:
            return FraudRiskLevel.MEDIUM
        else:
            return FraudRiskLevel.LOW
    
    def _generate_recommendations(
        self,
        risk_level: FraudRiskLevel,
        indicators: List[FraudIndicator]
    ) -> List[str]:
        """Generate recommendations based on fraud detection"""
        
        recommendations = []
        
        if risk_level == FraudRiskLevel.CRITICAL:
            recommendations.append("REJECT document immediately")
            recommendations.append("Flag user account for review")
            recommendations.append("Report to compliance team")
        elif risk_level == FraudRiskLevel.HIGH:
            recommendations.append("Require manual review by compliance officer")
            recommendations.append("Request additional verification documents")
            recommendations.append("Conduct enhanced due diligence")
        elif risk_level == FraudRiskLevel.MEDIUM:
            recommendations.append("Request higher quality document scan")
            recommendations.append("Verify data with secondary source")
        else:
            recommendations.append("Proceed with standard verification")
        
        # Specific recommendations for indicators
        if FraudIndicator.TAMPERING in indicators:
            recommendations.append("Document shows signs of digital manipulation")
        
        if FraudIndicator.POOR_QUALITY in indicators:
            recommendations.append("Request original document or higher resolution scan")
        
        if FraudIndicator.DUPLICATE in indicators:
            recommendations.append("Document matches previously flagged fraudulent document")
        
        return recommendations

# Initialize detector
fraud_detector = DocumentFraudDetector()

# API endpoints
@app.post("/api/v1/fraud/detect", response_model=FraudDetectionResult)
async def detect_document_fraud(
    file: UploadFile = File(...),
    document_type: str = "passport"
):
    """Detect fraud in uploaded document"""
    
    # Save uploaded file
    temp_path = Path(f"/tmp/fraud_check_{file.filename}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Detect fraud
    result = await fraud_detector.detect_fraud(temp_path, document_type)
    
    # Clean up
    temp_path.unlink()
    
    return result

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "document-fraud-detection",
        "version": "1.0.0",
        "deepseek_enabled": True,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8044)
