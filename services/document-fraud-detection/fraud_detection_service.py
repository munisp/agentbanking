#!/usr/bin/env python3
"""
POS-54agent Document Fraud Detection Service — Multi-layer document
authenticity verification using image forensics, metadata analysis,
and pattern matching.

Detection capabilities:
  - Digital manipulation detection (clone, splice, copy-move)
  - Font consistency analysis
  - EXIF/metadata anomaly detection
  - Print artifact analysis (dot patterns, color banding)
  - Security feature verification (watermarks, holograms, microprint)
  - Template matching against known genuine documents
  - Error Level Analysis (ELA) for compression artifacts
"""

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from PIL import Image, ImageChops, ImageStat
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fraud-detection")

app = FastAPI(title="POS-54agent Document Fraud Detection", version="1.0.0")


class FraudSeverity(str, Enum):
    CLEAN = "clean"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FraudIndicator:
    indicator_type: str
    description: str
    severity: FraudSeverity
    confidence: float
    location: Optional[str] = None
    evidence: Optional[dict] = None


@dataclass
class MetadataAnalysis:
    has_exif: bool
    creation_software: Optional[str]
    modification_software: Optional[str]
    creation_date: Optional[str]
    modification_date: Optional[str]
    gps_data: Optional[dict]
    suspicious_tags: list[str]
    metadata_score: float  # 0 = clean, 1 = suspicious
    analysis_status: str = "completed"


@dataclass
class ELAResult:
    """Error Level Analysis result."""
    max_difference: float
    mean_difference: float
    suspicious_regions: list[dict]
    ela_score: float  # 0 = uniform (clean), 1 = non-uniform (edited)
    analysis_status: str = "completed"


@dataclass
class FraudReport:
    request_id: str
    overall_score: float  # 0 = genuine, 1 = fraudulent
    severity: FraudSeverity
    verdict: str
    indicators: list[FraudIndicator]
    metadata_analysis: MetadataAnalysis
    ela_result: ELAResult
    font_analysis: dict
    security_features: dict
    template_match: dict
    recommendations: list[str]
    processing_time_ms: float


# EXIF tag ids
_EXIF_SOFTWARE = 305
_EXIF_DATETIME = 306
_EXIF_GPS_IFD = 34853

# Known image-editing software whose presence in metadata is a red flag for
# a document that should come straight from a camera/scanner.
_EDITING_SOFTWARE_KEYWORDS = (
    "photoshop", "gimp", "paint.net", "pixlr", "canva", "lightroom",
    "affinity", "paintshop", "illustrator", "inkscape",
)


class FraudDetectionEngine:
    """Multi-layer document fraud detection engine.

    Only analysis modules that perform real inspection of the submitted
    image bytes contribute to the overall score. Modules without a real
    implementation report status "not_available" and are excluded from
    scoring — they never contribute fabricated "clean" evidence.
    """

    def __init__(self):
        self.initialized = False
        self.known_templates = {}

    async def initialize(self):
        if self.initialized:
            return
        # Load known document templates for comparison
        self.known_templates = {
            "kenya_id_2014": {"aspect_ratio": 1.586, "color_profile": "cmyk", "security_features": 8},
            "kenya_passport_2019": {"aspect_ratio": 1.414, "color_profile": "cmyk", "security_features": 12},
            "kenya_dl_2020": {"aspect_ratio": 1.586, "color_profile": "cmyk", "security_features": 6},
        }
        self.initialized = True
        logger.info("Fraud detection engine initialized")

    async def analyze(self, image_bytes: bytes, document_type: Optional[str] = None) -> FraudReport:
        """Run full fraud analysis pipeline."""
        await self.initialize()
        if not PIL_AVAILABLE:
            # Fail closed: without image-forensics dependencies we cannot
            # analyze anything, and must never emit a fabricated verdict.
            raise HTTPException(
                status_code=503,
                detail="Document forensics unavailable: imaging dependencies "
                       "(Pillow) are not installed on this service"
            )
        start = time.monotonic()
        request_id = str(uuid.uuid4())

        # Run all analysis modules
        metadata = self._analyze_metadata(image_bytes)
        ela = self._error_level_analysis(image_bytes)
        fonts = self._analyze_fonts(image_bytes)
        security = self._check_security_features(image_bytes, document_type)
        template = self._template_match(image_bytes, document_type)

        # Collect indicators (only from modules that really ran)
        indicators = []

        if metadata.analysis_status == "completed" and metadata.metadata_score > 0.5:
            indicators.append(FraudIndicator(
                "metadata_anomaly", "Suspicious metadata detected",
                FraudSeverity.MEDIUM, metadata.metadata_score,
                evidence={"software": metadata.modification_software,
                          "suspicious_tags": metadata.suspicious_tags}
            ))

        if ela.analysis_status == "completed" and ela.ela_score > 0.6:
            indicators.append(FraudIndicator(
                "digital_manipulation", "Possible digital editing detected via ELA",
                FraudSeverity.HIGH, ela.ela_score,
                evidence={"suspicious_regions": len(ela.suspicious_regions)}
            ))

        if fonts.get("status") == "completed" and fonts.get("inconsistency_score", 0) > 0.4:
            indicators.append(FraudIndicator(
                "font_inconsistency", "Multiple font families detected where one expected",
                FraudSeverity.MEDIUM, fonts["inconsistency_score"],
            ))

        if security.get("status") == "completed" and not security.get("all_present", True):
            indicators.append(FraudIndicator(
                "missing_security_features",
                f"Missing {security.get('missing_count', 0)} expected security features",
                FraudSeverity.HIGH, 0.8,
                evidence={"missing": security.get('missing_features', [])}
            ))

        # Calculate overall score across the modules that actually ran,
        # renormalizing weights so unavailable modules contribute nothing.
        weighted = []
        if metadata.analysis_status == "completed":
            weighted.append((metadata.metadata_score, 0.15))
        if ela.analysis_status == "completed":
            weighted.append((ela.ela_score, 0.30))
        if fonts.get("status") == "completed":
            weighted.append((fonts.get("inconsistency_score", 0.0), 0.20))
        if security.get("status") == "completed":
            weighted.append((1 - security.get("match_score", 1.0), 0.20))
        if template.get("status") == "completed":
            weighted.append((1 - template.get("similarity", 1.0), 0.15))

        if not weighted:
            raise HTTPException(
                status_code=503,
                detail="No fraud analysis modules available for this document"
            )
        total_weight = sum(w for _, w in weighted)
        overall = min(sum(s * w for s, w in weighted) / total_weight, 1.0)

        full_coverage = len(weighted) == 5
        if overall < 0.15:
            severity = FraudSeverity.CLEAN
            verdict = "No fraud indicators detected in performed analyses"
            if not full_coverage:
                verdict += " (limited coverage: some checks unavailable)"
        elif overall < 0.35:
            severity = FraudSeverity.LOW
            verdict = "Minor anomalies detected — likely genuine"
        elif overall < 0.55:
            severity = FraudSeverity.MEDIUM
            verdict = "Moderate anomalies — manual review recommended"
        elif overall < 0.75:
            severity = FraudSeverity.HIGH
            verdict = "Significant fraud indicators — likely tampered"
        else:
            severity = FraudSeverity.CRITICAL
            verdict = "Strong evidence of fraud — document rejected"

        recommendations = []
        if not full_coverage:
            recommendations.append(
                "Some fraud checks were unavailable; do not treat this report "
                "as full verification — perform manual document review"
            )
        if severity in (FraudSeverity.MEDIUM, FraudSeverity.HIGH):
            recommendations.append("Request original physical document for in-person verification")
            recommendations.append("Cross-reference with issuing authority database")
        if severity == FraudSeverity.CRITICAL:
            recommendations.append("Flag account for fraud investigation")
            recommendations.append("Report to compliance team immediately")

        return FraudReport(
            request_id=request_id,
            overall_score=round(overall, 4),
            severity=severity,
            verdict=verdict,
            indicators=indicators,
            metadata_analysis=metadata,
            ela_result=ela,
            font_analysis=fonts,
            security_features=security,
            template_match=template,
            recommendations=recommendations,
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        )

    def _analyze_metadata(self, image_bytes: bytes) -> MetadataAnalysis:
        """Analyze image EXIF/metadata for anomalies (real inspection)."""
        suspicious_tags: list[str] = []
        creation_software = None
        modification_software = None
        creation_date = None
        modification_date = None
        gps_data = None
        has_exif = False

        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Submitted content is not a decodable image: {e}"
            )

        info = getattr(img, "info", {}) or {}
        exif = {}
        try:
            exif = img.getexif() or {}
        except Exception:
            exif = {}

        has_exif = bool(exif) or bool(info.get("exif"))

        raw_software = None
        try:
            raw_software = exif.get(_EXIF_SOFTWARE) or info.get("Software")
        except Exception:
            raw_software = info.get("Software")
        if raw_software:
            software_str = str(raw_software)
            if any(k in software_str.lower() for k in _EDITING_SOFTWARE_KEYWORDS):
                modification_software = software_str
                suspicious_tags.append(f"editing_software:{software_str}")
            else:
                creation_software = software_str

        try:
            creation_date = exif.get(_EXIF_DATETIME)
        except Exception:
            creation_date = None

        try:
            gps_ifd = exif.get_ifd(_EXIF_GPS_IFD) if exif else None
            if gps_ifd:
                gps_data = {str(k): str(v) for k, v in gps_ifd.items()}
        except Exception:
            gps_data = None

        # Scoring: editing software in metadata is a strong anomaly; complete
        # absence of metadata on an allegedly camera-captured ID document is
        # moderately suspicious (metadata is commonly stripped when editing).
        score = 0.0
        if modification_software:
            score += 0.6
        if not has_exif:
            score += 0.2
            suspicious_tags.append("no_exif_metadata")
        score = min(score, 1.0)

        return MetadataAnalysis(
            has_exif=has_exif,
            creation_software=creation_software,
            modification_software=modification_software,
            creation_date=str(creation_date) if creation_date else None,
            modification_date=None,
            gps_data=gps_data,
            suspicious_tags=suspicious_tags,
            metadata_score=score,
        )

    def _error_level_analysis(self, image_bytes: bytes) -> ELAResult:
        """Real Error Level Analysis: re-encode at known JPEG quality and
        measure per-pixel error levels. Edited regions re-compress
        differently and stand out."""
        try:
            original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Submitted content is not a decodable image: {e}"
            )

        buffer = io.BytesIO()
        try:
            original.save(buffer, "JPEG", quality=90)
        except Exception as e:
            logger.error(f"ELA re-encode failed: {e}")
            raise HTTPException(status_code=500, detail="ELA analysis failed")
        buffer.seek(0)
        resaved = Image.open(buffer).convert("RGB")

        diff = ImageChops.difference(original, resaved)
        gray = diff.convert("L")

        extrema = gray.getextrema()
        max_difference = float(extrema[1]) if extrema else 0.0
        mean_difference = float(ImageStat.Stat(gray).mean[0])

        # Block-level analysis: regions whose error level is far above the
        # global mean are candidate spliced/edited areas.
        suspicious_regions: list[dict] = []
        width, height = gray.size
        grid = 8
        if width >= grid and height >= grid and mean_difference > 0:
            bw, bh = max(width // grid, 1), max(height // grid, 1)
            for gy in range(grid):
                for gx in range(grid):
                    box = (gx * bw, gy * bh, min((gx + 1) * bw, width), min((gy + 1) * bh, height))
                    block_mean = float(ImageStat.Stat(gray.crop(box)).mean[0])
                    if block_mean > max(2.5 * mean_difference, mean_difference + 10.0) and block_mean > 15.0:
                        suspicious_regions.append({
                            "box": list(box),
                            "mean_difference": round(block_mean, 2),
                        })

        # Heuristic normalization of ELA evidence into [0, 1]
        ela_score = min(max((mean_difference - 2.0) / 13.0, 0.0), 1.0)
        if suspicious_regions:
            ela_score = min(ela_score + 0.25 * len(suspicious_regions) / 4.0, 1.0)

        return ELAResult(
            max_difference=round(max_difference, 2),
            mean_difference=round(mean_difference, 2),
            suspicious_regions=suspicious_regions,
            ela_score=round(ela_score, 4),
        )

    def _analyze_fonts(self, image_bytes: bytes) -> dict:
        """Font consistency analysis requires OCR; no OCR engine is integrated
        in this service, so this module is explicitly unavailable rather than
        returning fabricated consistency scores."""
        return {
            "status": "not_available",
            "reason": "No OCR/font-analysis engine integrated; fonts were not analyzed"
        }

    def _check_security_features(self, image_bytes: bytes, doc_type: Optional[str]) -> dict:
        """Security feature verification requires specialized sensors/models
        (UV, hologram, microprint). Not integrated; explicitly unavailable."""
        return {
            "status": "not_available",
            "reason": "No security-feature detection model integrated; "
                      "security features were not verified"
        }

    def _template_match(self, image_bytes: bytes, doc_type: Optional[str]) -> dict:
        """Template matching against known genuine documents requires a
        template image store; only metadata profiles are configured, so this
        module is explicitly unavailable."""
        return {
            "status": "not_available",
            "reason": "No genuine document template images configured; "
                      "template matching was not performed"
        }


engine = FraudDetectionEngine()


class FraudCheckRequest(BaseModel):
    image_base64: str
    document_type: Optional[str] = None


@app.post("/fraud/analyze")
async def analyze_document(req: FraudCheckRequest):
    image_bytes = base64.b64decode(req.image_base64)
    report = await engine.analyze(image_bytes, req.document_type)
    return asdict(report)


@app.post("/fraud/quick-check")
async def quick_check(req: FraudCheckRequest):
    """Fast check — metadata + ELA only."""
    await engine.initialize()
    if not PIL_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Document forensics unavailable: imaging dependencies "
                   "(Pillow) are not installed on this service"
        )
    image_bytes = base64.b64decode(req.image_base64)
    metadata = engine._analyze_metadata(image_bytes)
    ela = engine._error_level_analysis(image_bytes)
    score = metadata.metadata_score * 0.4 + ela.ela_score * 0.6
    return {
        "score": round(score, 4),
        "suspicious": score > 0.4,
        "metadata_score": metadata.metadata_score,
        "ela_score": ela.ela_score,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "document-fraud-detection", "engine_initialized": engine.initialized}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8106"))
    uvicorn.run(app, host="0.0.0.0", port=port)
