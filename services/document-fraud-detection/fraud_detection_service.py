#!/usr/bin/env python3
"""
POS-54agent Document Fraud Detection Service — Multi-layer document
authenticity verification using image forensics, metadata analysis,
and pattern matching.

Detection capabilities:
  - Digital manipulation detection (clone, splice, copy-move)
  - EXIF/metadata anomaly detection (real, via PIL)
  - Error Level Analysis (ELA) for compression artifacts (real, via PIL)

FAIL-CLOSED POLICY: modules that cannot genuinely evaluate the submitted
image (font analysis, security features, template matching - all of which
require trained detectors/OCR that are not deployed here) report
"performed: false" and force an INCONCLUSIVE verdict with manual review.
This service NEVER returns a constant "appears genuine" verdict that
ignores the image bytes. If the imaging stack is unavailable, the API
returns HTTP 503.
"""

import asyncio
import base64
import binascii
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fraud-detection")

app = FastAPI(title="POS-54agent Document Fraud Detection", version="1.0.0")


class AnalysisUnavailableError(Exception):
    """Raised when the image analysis stack cannot run (e.g. PIL missing
    or the payload is not a decodable image). Mapped to HTTP 503."""
    pass


def _load_image(image_bytes: bytes):
    """Decode image bytes with PIL. Raises AnalysisUnavailableError on
    any failure - never silently analyzes nothing."""
    try:
        from PIL import Image
    except ImportError as e:
        raise AnalysisUnavailableError(
            "PIL/Pillow imaging stack is not installed; forensic analysis cannot run"
        ) from e
    try:
        return Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise AnalysisUnavailableError(f"Submitted payload is not a decodable image: {e}") from e


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


@dataclass
class ELAResult:
    """Error Level Analysis result."""
    max_difference: float
    mean_difference: float
    suspicious_regions: list[dict]
    ela_score: float  # 0 = uniform (clean), 1 = non-uniform (edited)


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


# Software known to be used for image editing (metadata red flag)
_EDITING_SOFTWARE_KEYWORDS = (
    "photoshop", "gimp", "lightroom", "affinity", "paint.net",
    "pixlr", "canva", "corel", "illustrator"
)


class FraudDetectionEngine:
    """Multi-layer document fraud detection engine."""

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
        """Run full fraud analysis pipeline.

        Fail-closed: only modules that genuinely inspected image_bytes
        contribute a "genuine" signal. Modules that are not implemented
        (font/security/template) force an inconclusive verdict.
        """
        await self.initialize()
        start = time.monotonic()
        request_id = str(uuid.uuid4())

        # Real forensic modules (raise AnalysisUnavailableError -> HTTP 503
        # if the imaging stack cannot process the bytes)
        metadata = self._analyze_metadata(image_bytes)
        ela = self._error_level_analysis(image_bytes)

        # Modules requiring detectors/OCR that are not deployed here.
        # These honestly report performed=False instead of fabricated
        # constant results.
        fonts = self._analyze_fonts(image_bytes)
        security = self._check_security_features(image_bytes, document_type)
        template = self._template_match(image_bytes, document_type)

        # Collect indicators
        indicators = []

        if metadata.metadata_score > 0.5:
            indicators.append(FraudIndicator(
                "metadata_anomaly", "Suspicious metadata detected",
                FraudSeverity.MEDIUM, metadata.metadata_score,
                evidence={
                    "software": metadata.modification_software,
                    "suspicious_tags": metadata.suspicious_tags,
                }
            ))

        if ela.ela_score > 0.6:
            indicators.append(FraudIndicator(
                "digital_manipulation", "Possible digital editing detected via ELA",
                FraudSeverity.HIGH, ela.ela_score,
                evidence={"mean_difference": ela.mean_difference}
            ))

        if fonts.get("performed") and fonts.get("inconsistency_score", 0) > 0.4:
            indicators.append(FraudIndicator(
                "font_inconsistency", "Multiple font families detected where one expected",
                FraudSeverity.MEDIUM, fonts["inconsistency_score"],
            ))

        if security.get("performed") and not security.get("all_present", True):
            indicators.append(FraudIndicator(
                "missing_security_features",
                f"Missing {security.get('missing_count', 0)} expected security features",
                FraudSeverity.HIGH, 0.8,
                evidence={"missing": security.get("missing_features", [])}
            ))

        # Calculate overall score from PERFORMED modules only, renormalizing
        # weights so unperformed modules never contribute a fake "clean" 0.
        weighted = [(metadata.metadata_score, 0.15), (ela.ela_score, 0.30)]
        if fonts.get("performed"):
            weighted.append((fonts.get("inconsistency_score", 0), 0.20))
        if security.get("performed"):
            weighted.append(((1 - security.get("match_score", 1)), 0.20))
        if template.get("performed"):
            weighted.append(((1 - template.get("similarity", 1)), 0.15))

        weight_total = sum(w for _, w in weighted)
        overall = min(sum(s * w for s, w in weighted) / weight_total, 1.0) if weight_total else 1.0

        analysis_complete = (
            fonts.get("performed") and security.get("performed") and template.get("performed")
        )

        if not analysis_complete:
            indicators.append(FraudIndicator(
                "analysis_incomplete",
                "Font, security-feature and template analysis were not performed; "
                "verdict is based on metadata and ELA forensics only",
                FraudSeverity.MEDIUM, 1.0,
            ))

        if not analysis_complete:
            # Fail-closed: partial analysis can NEVER clear a document.
            severity = FraudSeverity.MEDIUM if overall < 0.75 else FraudSeverity.HIGH
            verdict = (
                "Inconclusive — partial forensic analysis only (metadata + ELA); "
                "manual review required"
            )
        elif overall < 0.15:
            severity = FraudSeverity.CLEAN
            verdict = "Document appears genuine"
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
        if not analysis_complete:
            recommendations.append("Route to manual document review — automated analysis was partial")
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
        """Analyze real image EXIF/metadata for anomalies using PIL.

        Raises AnalysisUnavailableError if the image cannot be decoded -
        never returns a constant fabricated metadata report.
        """
        img = _load_image(image_bytes)

        suspicious_tags: list[str] = []
        creation_software = None
        modification_software = None
        creation_date = None
        modification_date = None
        gps_data = None

        exif = {}
        try:
            exif = dict(img.getexif() or {})
        except Exception as e:
            logger.warning(f"Could not read EXIF tags: {e}")

        has_exif = bool(exif)

        # Tag 0x0131 = Software, 0x0132 = DateTime, 0x010F = Make, 0x0110 = Model
        software = exif.get(0x0131)
        if software:
            software_str = str(software)
            modification_software = software_str
            lowered = software_str.lower()
            if any(k in lowered for k in _EDITING_SOFTWARE_KEYWORDS):
                suspicious_tags.append(f"editing_software:{software_str}")

        dt = exif.get(0x0132)
        if dt:
            creation_date = str(dt)

        if exif.get(0x010F) or exif.get(0x0110):
            creation_software = f"{exif.get(0x010F, '')} {exif.get(0x0110, '')}".strip() or "Camera"

        try:
            gps_ifd = img.getexif().get_ifd(0x8825) if hasattr(img.getexif(), "get_ifd") else {}
            if gps_ifd:
                gps_data = {"raw_tags_present": len(gps_ifd)}
        except Exception:
            gps_data = None

        # PNG and other non-camera formats legitimately carry no EXIF; for a
        # purported photographed ID document, total absence of capture
        # metadata is a moderate anomaly, not proof of fraud.
        fmt = (img.format or "").upper()
        if suspicious_tags:
            metadata_score = 0.8
        elif not has_exif and fmt in ("JPEG", "JPG", "TIFF"):
            metadata_score = 0.4
        elif not has_exif:
            metadata_score = 0.2
        else:
            metadata_score = 0.05

        return MetadataAnalysis(
            has_exif=has_exif,
            creation_software=creation_software,
            modification_software=modification_software,
            creation_date=creation_date,
            modification_date=modification_date,
            gps_data=gps_data,
            suspicious_tags=suspicious_tags,
            metadata_score=metadata_score,
        )

    def _error_level_analysis(self, image_bytes: bytes) -> ELAResult:
        """Real Error Level Analysis: recompress the image at a known JPEG
        quality and measure the per-pixel difference. Edited regions
        recompress differently from the rest of the image.

        Raises AnalysisUnavailableError if the image cannot be processed.
        """
        from PIL import ImageChops, ImageStat

        img = _load_image(image_bytes).convert("RGB")

        buffer = io.BytesIO()
        try:
            img.save(buffer, "JPEG", quality=90)
        except Exception as e:
            raise AnalysisUnavailableError(f"ELA recompression failed: {e}") from e
        buffer.seek(0)
        recompressed = _load_image(buffer.read()).convert("RGB")

        diff = ImageChops.difference(img, recompressed).convert("L")
        stat = ImageStat.Stat(diff)
        mean_difference = float(stat.mean[0])
        max_difference = float(diff.getextrema()[1])

        # Count strongly-deviating pixels as a proxy for edited regions.
        histogram = diff.histogram()
        total_pixels = max(diff.size[0] * diff.size[1], 1)
        hot_pixels = sum(histogram[32:])  # buckets with diff >= 32
        hot_ratio = hot_pixels / total_pixels

        suspicious_regions: list[dict] = []
        if hot_ratio > 0.02:
            suspicious_regions.append({
                "description": "Region(s) with abnormal recompression error",
                "hot_pixel_ratio": round(hot_ratio, 4),
            })

        # Score: mean ELA difference for an untouched camera image is
        # typically low and uniform; high mean or many hot pixels indicates
        # resaving/editing. Saturates at 1.0.
        ela_score = min((mean_difference / 12.0) + (hot_ratio * 4.0), 1.0)

        return ELAResult(
            max_difference=round(max_difference, 2),
            mean_difference=round(mean_difference, 2),
            suspicious_regions=suspicious_regions,
            ela_score=round(ela_score, 4),
        )

    def _analyze_fonts(self, image_bytes: bytes) -> dict:
        """Font consistency analysis requires OCR + font classification
        models that are not deployed in this service. Honestly report that
        the analysis was not performed instead of returning constant
        fabricated scores."""
        return {
            "performed": False,
            "reason": "Font analysis requires OCR/font-classification models not deployed in this service",
        }

    def _check_security_features(self, image_bytes: bytes, doc_type: Optional[str]) -> dict:
        """Security feature verification (hologram, microprint, UV pattern,
        etc.) requires trained detectors and, for some features, physical
        light sources - none of which are available here. Honestly report
        that the check was not performed instead of fabricating presence
        confidences."""
        return {
            "performed": False,
            "reason": "Security-feature detectors are not deployed; manual/physical inspection required",
            "manual_review_required": True,
        }

    def _template_match(self, image_bytes: bytes, doc_type: Optional[str]) -> dict:
        """Template matching requires reference scans of genuine documents,
        which are not loaded in this service. Honestly report that matching
        was not performed instead of returning a constant similarity."""
        return {
            "performed": False,
            "reason": "No genuine reference templates loaded; template matching not performed",
        }


engine = FraudDetectionEngine()


class FraudCheckRequest(BaseModel):
    image_base64: str
    document_type: Optional[str] = None


@app.post("/fraud/analyze")
async def analyze_document(req: FraudCheckRequest):
    try:
        image_bytes = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="image_base64 is not valid base64")
    try:
        report = await engine.analyze(image_bytes, req.document_type)
    except AnalysisUnavailableError as e:
        logger.error(f"Fraud analysis unavailable: {e}")
        raise HTTPException(status_code=503, detail=f"Fraud analysis unavailable: {e}")
    return asdict(report)


@app.post("/fraud/quick-check")
async def quick_check(req: FraudCheckRequest):
    """Fast check — metadata + ELA only (both real)."""
    await engine.initialize()
    try:
        image_bytes = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="image_base64 is not valid base64")
    try:
        metadata = engine._analyze_metadata(image_bytes)
        ela = engine._error_level_analysis(image_bytes)
    except AnalysisUnavailableError as e:
        logger.error(f"Fraud quick-check unavailable: {e}")
        raise HTTPException(status_code=503, detail=f"Fraud analysis unavailable: {e}")
    score = metadata.metadata_score * 0.4 + ela.ela_score * 0.6
    return {
        "score": round(score, 4),
        "suspicious": score > 0.4,
        "metadata_score": metadata.metadata_score,
        "ela_score": ela.ela_score,
        "partial_analysis": True,
        "note": "Quick check is metadata+ELA only; it cannot clear a document. Use /fraud/analyze plus manual review.",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "document-fraud-detection", "engine_initialized": engine.initialized}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8106"))
    uvicorn.run(app, host="0.0.0.0", port=port)
