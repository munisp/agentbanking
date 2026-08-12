#!/usr/bin/env python3
"""
POS-54agent VLM Document Understanding Service — Vision Language Model integration
for intelligent document analysis, verification, and fraud detection.

Uses multimodal LLMs (GPT-4V, Gemini Pro Vision, LLaVA) to:
  - Understand document layout and content semantically
  - Cross-verify OCR results with visual understanding
  - Detect document anomalies and potential fraud
  - Extract complex/non-standard fields that regex cannot handle
  - Classify documents by type and issuing authority

NOTE: This service performs REAL VLM inference against the configured
backend (BUILT_IN_FORGE_API_URL / BUILT_IN_FORGE_API_KEY). When no backend
is configured or inference fails, endpoints return HTTP 503 — the service
never fabricates analysis results and never defaults to VERIFIED.
"""

import asyncio
import base64
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
logger = logging.getLogger("vlm-document")

app = FastAPI(title="POS-54agent VLM Document Service", version="1.0.0")


# ── Models ────────────────────────────────────────────────────────────────────

class VerificationResult(str, Enum):
    VERIFIED = "verified"
    SUSPICIOUS = "suspicious"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class FraudIndicator(str, Enum):
    FONT_INCONSISTENCY = "font_inconsistency"
    ALIGNMENT_ISSUES = "alignment_issues"
    PHOTO_TAMPERING = "photo_tampering"
    TEXT_OVERLAY = "text_overlay"
    DIGITAL_MANIPULATION = "digital_manipulation"
    MISSING_SECURITY_FEATURES = "missing_security_features"
    METADATA_MISMATCH = "metadata_mismatch"
    COLOR_ANOMALY = "color_anomaly"


@dataclass
class VLMAnalysis:
    request_id: str
    document_type: str
    issuing_authority: str
    document_language: str
    extracted_data: dict
    ocr_cross_verification: dict
    fraud_indicators: list[dict]
    fraud_score: Optional[float]  # 0.0 (clean) to 1.0 (fraudulent); None when the VLM did not provide one
    verification_result: VerificationResult
    visual_quality_assessment: dict
    confidence: Optional[float]
    reasoning: str
    processing_time_ms: float


# ── VLM Engine ────────────────────────────────────────────────────────────────

class VLMEngine:
    """Multi-provider VLM engine for document understanding."""

    DOCUMENT_ANALYSIS_PROMPT = """You are an expert document verification analyst. Analyze this document image and provide:

1. **Document Classification**: Type, issuing country/authority, document series/version
2. **Data Extraction**: All visible text fields with their values
3. **Visual Verification**:
   - Font consistency across all text elements
   - Alignment of text blocks, photos, and security features
   - Color consistency and gradient patterns
   - Photo quality and potential tampering signs
   - Presence of expected security features (holograms, microprint, UV patterns)
4. **Fraud Assessment**:
   - Score from 0.0 (genuine) to 1.0 (fraudulent)
   - Specific indicators found
   - Confidence in assessment
5. **Cross-verification**: Compare extracted text with expected patterns for this document type

Respond in JSON format with these exact keys:
{
  "document_type": "string",
  "issuing_authority": "string",
  "document_language": "string",
  "extracted_data": {},
  "fraud_indicators": [{"type": "string", "description": "string", "severity": "low|medium|high", "location": "string"}],
  "fraud_score": 0.0,
  "confidence": 0.0,
  "visual_quality": {"resolution": "string", "lighting": "string", "focus": "string", "angle": "string"},
  "security_features_found": [],
  "security_features_missing": [],
  "reasoning": "string"
}"""

    OCR_VERIFICATION_PROMPT = """Compare the following OCR-extracted text with what you can see in the document image.
For each field, indicate if the OCR result matches the visual content.

OCR Results:
{ocr_data}

Respond in JSON:
{{
  "field_verifications": [
    {{"field": "string", "ocr_value": "string", "visual_value": "string", "match": true/false, "confidence": 0.0-1.0}}
  ],
  "overall_match_score": 0.0-1.0,
  "discrepancies": ["string"]
}}"""

    def __init__(self):
        self.api_url = os.getenv("BUILT_IN_FORGE_API_URL", "")
        self.api_key = os.getenv("BUILT_IN_FORGE_API_KEY", "")

    def _backend_configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    async def analyze_document(self, image_base64: str, ocr_data: Optional[dict] = None) -> VLMAnalysis:
        """Run full VLM analysis on a document image.

        Performs real VLM inference. Raises HTTP 503 when the VLM backend is
        not configured or the call fails — never fabricates an analysis and
        never defaults the verification result to VERIFIED.
        """
        start = time.monotonic()
        request_id = str(uuid.uuid4())

        if not self._backend_configured():
            raise HTTPException(
                status_code=503,
                detail=(
                    "VLM backend not configured "
                    "(BUILT_IN_FORGE_API_URL / BUILT_IN_FORGE_API_KEY missing). "
                    "Document analysis cannot be performed."
                ),
            )

        try:
            analysis_data = await self._call_vlm(self.DOCUMENT_ANALYSIS_PROMPT, image_base64)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"VLM inference failed: {e}")
            raise HTTPException(status_code=503, detail=f"VLM inference unavailable: {e}")

        if not isinstance(analysis_data, dict):
            raise HTTPException(status_code=503, detail="VLM returned an unparseable response")

        # Cross-verify with OCR if provided
        ocr_verification = {}
        if ocr_data:
            ocr_verification = self._cross_verify_ocr(analysis_data.get("extracted_data", {}), ocr_data)

        fraud_indicators = [
            {
                "type": ind.get("type", "unknown"),
                "description": ind.get("description", ""),
                "severity": ind.get("severity", "low"),
                "location": ind.get("location", ""),
            }
            for ind in analysis_data.get("fraud_indicators", [])
            if isinstance(ind, dict)
        ]

        # Use the model-reported fraud score only. If the VLM did not return a
        # score, the document goes to NEEDS_REVIEW — never default VERIFIED.
        fraud_score = analysis_data.get("fraud_score")
        if isinstance(fraud_score, (int, float)):
            fraud_score = float(fraud_score)
            if fraud_score > 0.7:
                verification = VerificationResult.REJECTED
            elif fraud_score > 0.4:
                verification = VerificationResult.SUSPICIOUS
            elif fraud_score > 0.2:
                verification = VerificationResult.NEEDS_REVIEW
            else:
                verification = VerificationResult.VERIFIED
        else:
            logger.warning("VLM response missing fraud_score; marking document as needs_review")
            fraud_score = None
            verification = VerificationResult.NEEDS_REVIEW

        confidence = analysis_data.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else None

        return VLMAnalysis(
            request_id=request_id,
            document_type=analysis_data.get("document_type", "unknown"),
            issuing_authority=analysis_data.get("issuing_authority", "unknown"),
            document_language=analysis_data.get("document_language", "unknown"),
            extracted_data=analysis_data.get("extracted_data", {}),
            ocr_cross_verification=ocr_verification,
            fraud_indicators=fraud_indicators,
            fraud_score=fraud_score,
            verification_result=verification,
            visual_quality_assessment=analysis_data.get("visual_quality", {}),
            confidence=confidence,
            reasoning=analysis_data.get("reasoning", ""),
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        )

    def _cross_verify_ocr(self, vlm_data: dict, ocr_data: dict) -> dict:
        """Cross-verify VLM extraction with OCR results."""
        verifications = []
        for key, vlm_value in vlm_data.items():
            if isinstance(vlm_value, bool):
                continue
            ocr_value = ocr_data.get(key, "")
            match = str(vlm_value).upper().strip() == str(ocr_value).upper().strip()
            verifications.append({
                "field": key,
                "vlm_value": str(vlm_value),
                "ocr_value": str(ocr_value),
                "match": match,
            })

        matches = sum(1 for v in verifications if v["match"])
        total = len(verifications)

        return {
            "field_verifications": verifications,
            "overall_match_score": round(matches / total, 2) if total else None,
            "discrepancies": [v["field"] for v in verifications if not v["match"]],
        }

    async def _call_vlm(self, prompt: str, image_base64: str) -> dict:
        """Call the VLM API (production implementation)."""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            payload = {
                "messages": [
                    {"role": "system", "content": "You are a document verification expert."},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    ]},
                ],
                "response_format": {"type": "json_object"},
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            async with session.post(f"{self.api_url}/v1/chat/completions", json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"VLM backend returned HTTP {resp.status}: {body[:500]}")
                data = await resp.json()
                return json.loads(data["choices"][0]["message"]["content"])


# ── API ───────────────────────────────────────────────────────────────────────

vlm_engine = VLMEngine()


class VLMRequest(BaseModel):
    image_base64: str
    ocr_data: Optional[dict] = None
    document_type_hint: Optional[str] = None


@app.post("/vlm/analyze")
async def analyze_document(req: VLMRequest):
    """Full VLM document analysis with fraud detection."""
    result = await vlm_engine.analyze_document(req.image_base64, req.ocr_data)
    return asdict(result)


@app.post("/vlm/verify-ocr")
async def verify_ocr(req: VLMRequest):
    """Cross-verify OCR results against visual document content."""
    if not req.ocr_data:
        raise HTTPException(400, "ocr_data required for verification")
    result = await vlm_engine.analyze_document(req.image_base64, req.ocr_data)
    return {
        "request_id": result.request_id,
        "ocr_verification": result.ocr_cross_verification,
        "processing_time_ms": result.processing_time_ms,
    }


@app.post("/vlm/classify")
async def classify_document(req: VLMRequest):
    """Classify document type and issuing authority."""
    result = await vlm_engine.analyze_document(req.image_base64)
    return {
        "request_id": result.request_id,
        "document_type": result.document_type,
        "issuing_authority": result.issuing_authority,
        "language": result.document_language,
        "confidence": result.confidence,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy" if vlm_engine._backend_configured() else "degraded",
        "service": "vlm-document",
        "version": "1.0.0",
        "vlm_configured": vlm_engine._backend_configured(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8102"))
    uvicorn.run(app, host="0.0.0.0", port=port)
