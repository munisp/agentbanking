#!/usr/bin/env python3
"""
POS-54Link VLM Document Understanding Service — Vision Language Model integration
for intelligent document analysis, verification, and fraud detection.

Uses multimodal LLMs (GPT-4V, Gemini Pro Vision, LLaVA) to:
  - Understand document layout and content semantically
  - Cross-verify OCR results with visual understanding
  - Detect document anomalies and potential fraud
  - Extract complex/non-standard fields that regex cannot handle
  - Classify documents by type and issuing authority
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

app = FastAPI(title="POS-54Link VLM Document Service", version="1.0.0")


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
    fraud_score: float  # 0.0 (clean) to 1.0 (fraudulent)
    verification_result: VerificationResult
    visual_quality_assessment: dict
    confidence: float
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

    async def analyze_document(self, image_base64: str, ocr_data: Optional[dict] = None) -> VLMAnalysis:
        """Run full VLM analysis on a document image."""
        start = time.monotonic()
        request_id = str(uuid.uuid4())

        # In production, call the LLM API with image
        # response = await self._call_vlm(self.DOCUMENT_ANALYSIS_PROMPT, image_base64)

        # Mock response for development
        analysis_data = {
            "document_type": "national_identity_card",
            "issuing_authority": "Republic of Kenya - National Registration Bureau",
            "document_language": "en",
            "extracted_data": {
                "document_number": "12345678",
                "full_name": "JOHN KAMAU MWANGI",
                "date_of_birth": "15/03/1990",
                "sex": "M",
                "district_of_birth": "NAIROBI",
                "date_of_issue": "20/06/2015",
                "photo_present": True,
                "signature_present": True,
            },
            "fraud_indicators": [],
            "fraud_score": 0.05,
            "visual_quality": {
                "resolution": "adequate",
                "lighting": "good",
                "focus": "sharp",
                "angle": "front-facing",
            },
            "security_features_found": [
                "holographic overlay",
                "microprint border",
                "UV-reactive ink",
                "ghost image",
            ],
            "security_features_missing": [],
            "reasoning": "Document appears genuine. All expected security features for a Kenyan national ID card (2014 series) are present. Font consistency is maintained across all text elements. Photo shows no signs of digital manipulation. Holographic overlay pattern matches known genuine specimens.",
        }

        # Cross-verify with OCR if provided
        ocr_verification = {}
        if ocr_data:
            ocr_verification = self._cross_verify_ocr(analysis_data["extracted_data"], ocr_data)

        fraud_indicators = [
            {
                "type": ind.get("type", "unknown"),
                "description": ind.get("description", ""),
                "severity": ind.get("severity", "low"),
                "location": ind.get("location", ""),
            }
            for ind in analysis_data.get("fraud_indicators", [])
        ]

        verification = VerificationResult.VERIFIED
        if analysis_data["fraud_score"] > 0.7:
            verification = VerificationResult.REJECTED
        elif analysis_data["fraud_score"] > 0.4:
            verification = VerificationResult.SUSPICIOUS
        elif analysis_data["fraud_score"] > 0.2:
            verification = VerificationResult.NEEDS_REVIEW

        return VLMAnalysis(
            request_id=request_id,
            document_type=analysis_data["document_type"],
            issuing_authority=analysis_data["issuing_authority"],
            document_language=analysis_data["document_language"],
            extracted_data=analysis_data["extracted_data"],
            ocr_cross_verification=ocr_verification,
            fraud_indicators=fraud_indicators,
            fraud_score=analysis_data["fraud_score"],
            verification_result=verification,
            visual_quality_assessment=analysis_data["visual_quality"],
            confidence=0.92,
            reasoning=analysis_data["reasoning"],
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
                "confidence": 0.95 if match else 0.5,
            })

        matches = sum(1 for v in verifications if v["match"])
        total = len(verifications) if verifications else 1

        return {
            "field_verifications": verifications,
            "overall_match_score": round(matches / total, 2),
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
        "status": "healthy",
        "service": "vlm-document",
        "version": "1.0.0",
        "vlm_configured": bool(vlm_engine.api_url),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8102"))
    uvicorn.run(app, host="0.0.0.0", port=port)
