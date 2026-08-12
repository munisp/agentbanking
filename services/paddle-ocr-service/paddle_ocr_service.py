#!/usr/bin/env python3
"""
POS-54agent PaddleOCR Service — Production-grade document text extraction
for KYC/KYB workflows. Supports ID cards, passports, utility bills, and
business registration documents across 80+ languages.

Endpoints:
  POST /ocr/extract       — Full document OCR with structured output
  POST /ocr/id-card       — Specialized ID card extraction (MRZ, fields)
  POST /ocr/passport      — Passport MRZ + VIZ extraction
  POST /ocr/utility-bill  — Utility bill address/name extraction
  POST /ocr/business-doc  — Business registration document parsing
  GET  /health            — Health check

NOTE: This service never returns fabricated OCR output. If the PaddleOCR
engine is not installed/configured, extraction endpoints return HTTP 503.
MRZ check digits are verified per ICAO 9303; no fixture data is served on
live paths.
"""

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("paddle-ocr")

app = FastAPI(title="POS-54agent PaddleOCR Service", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Models ────────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    ID_CARD = "id_card"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    BUSINESS_REGISTRATION = "business_registration"
    TAX_CERTIFICATE = "tax_certificate"
    PROOF_OF_ADDRESS = "proof_of_address"
    UNKNOWN = "unknown"


class OCRConfidence(str, Enum):
    HIGH = "high"       # > 0.95
    MEDIUM = "medium"   # 0.80 - 0.95
    LOW = "low"         # < 0.80


@dataclass
class TextRegion:
    text: str
    confidence: float
    bbox: list  # [x1, y1, x2, y2]
    field_name: Optional[str] = None


@dataclass
class DocumentField:
    field_name: str
    value: str
    confidence: float
    source_region: Optional[TextRegion] = None
    validated: bool = False
    validation_method: Optional[str] = None


@dataclass
class MRZData:
    raw_lines: list[str]
    document_type: str
    country_code: str
    surname: str
    given_names: str
    document_number: str
    nationality: str
    date_of_birth: str
    sex: str
    expiry_date: str
    personal_number: Optional[str] = None
    check_digits_valid: bool = False


@dataclass
class OCRResult:
    request_id: str
    document_type: DocumentType
    language: str
    text_regions: list[TextRegion]
    extracted_fields: list[DocumentField]
    mrz_data: Optional[MRZData] = None
    full_text: str = ""
    confidence_overall: float = 0.0
    confidence_level: OCRConfidence = OCRConfidence.LOW
    processing_time_ms: float = 0.0
    image_quality_score: float = 0.0
    warnings: list[str] = field(default_factory=list)


# ── OCR Engine ────────────────────────────────────────────────────────────────

class PaddleOCREngine:
    """Wraps PaddlePaddle OCR with document-specific extraction pipelines."""

    def __init__(self):
        self.initialized = False
        self.ocr = None
        self.init_error: Optional[str] = None

    async def initialize(self):
        """Lazy-load PaddleOCR models. Fails closed: no mock fallback."""
        if self.initialized:
            return
        try:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang=os.getenv("PADDLE_OCR_LANG", "en"),
                use_gpu=os.getenv("PADDLE_OCR_USE_GPU", "false").lower() == "true",
                det_model_dir=os.getenv("PADDLE_OCR_DET_MODEL_DIR") or None,
                rec_model_dir=os.getenv("PADDLE_OCR_REC_MODEL_DIR") or None,
                cls_model_dir=os.getenv("PADDLE_OCR_CLS_MODEL_DIR") or None,
                det_db_thresh=0.3,
                det_db_box_thresh=0.6,
                det_db_unclip_ratio=1.5,
                rec_batch_num=6,
                max_text_length=25,
                use_space_char=True,
                show_log=False,
            )
            self.initialized = True
            self.init_error = None
            logger.info("PaddleOCR engine initialized (models loaded)")
        except Exception as e:
            self.init_error = str(e)
            self.ocr = None
            self.initialized = False
            logger.error(f"PaddleOCR engine unavailable: {e}")

    async def extract_text(self, image_bytes: bytes, lang: str = "en") -> list[TextRegion]:
        """Run OCR on image bytes, return text regions with bounding boxes.

        Raises HTTP 503 when the OCR engine is unavailable — never returns
        canned/fixture text for real requests.
        """
        await self.initialize()

        if not self.initialized or self.ocr is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "OCR engine unavailable: "
                    f"{self.init_error or 'PaddleOCR is not installed or failed to initialize'}. "
                    "Text extraction cannot be performed."
                ),
            )

        import numpy as np
        from PIL import Image

        try:
            img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

        try:
            result = self.ocr.ocr(img, cls=True)
        except Exception as e:
            logger.error(f"PaddleOCR inference failed: {e}")
            raise HTTPException(status_code=503, detail=f"OCR inference failed: {e}")

        regions: list[TextRegion] = []
        for page in result or []:
            for line in page or []:
                bbox_pts = line[0]
                text = line[1][0]
                conf = float(line[1][1])
                xs = [p[0] for p in bbox_pts]
                ys = [p[1] for p in bbox_pts]
                regions.append(TextRegion(
                    text=text,
                    confidence=conf,
                    bbox=[min(xs), min(ys), max(xs), max(ys)],
                ))
        return regions

    def assess_image_quality(self, image_bytes: bytes) -> float:
        """Assess image quality (blur, lighting, resolution) using real image
        statistics — Laplacian-variance blur estimate, brightness balance and
        resolution adequacy. Raises HTTP 400 for undecodable images."""
        import numpy as np
        from PIL import Image

        try:
            img = np.array(Image.open(io.BytesIO(image_bytes)).convert("L"), dtype=np.float64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

        # Laplacian variance (blur detection) via a 3x3 kernel, no cv2 dependency
        padded = np.pad(img, 1, mode="edge")
        lap = (
            padded[:-2, 1:-1]
            + padded[1:-1, :-2]
            - 4.0 * padded[1:-1, 1:-1]
            + padded[1:-1, 2:]
            + padded[2:, 1:-1]
        )
        laplacian_var = float(lap.var())
        brightness = float(img.mean())
        pixels = int(img.shape[0] * img.shape[1])

        blur_score = min(1.0, laplacian_var / 500.0)
        brightness_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
        resolution_score = min(1.0, pixels / float(640 * 480))

        score = 0.5 * blur_score + 0.3 * brightness_score + 0.2 * resolution_score
        return round(max(0.0, min(1.0, score)), 4)


# ── Field Extraction Pipelines ────────────────────────────────────────────────

class IDCardExtractor:
    """Extract structured fields from national ID cards."""

    FIELD_PATTERNS = {
        "id_number": [r"ID\s*(?:NO|NUMBER)?[:\s]*(\d{6,12})", r"(\d{8,12})"],
        "full_name": [r"(?:FULL\s*)?NAME[:\s]*([A-Z\s]+)", r"([A-Z]{2,}\s+[A-Z]{2,}\s*[A-Z]*)"],
        "date_of_birth": [r"(?:DATE\s*OF\s*BIRTH|DOB)[:\s]*([\d/.-]+)", r"(\d{2}[/.-]\d{2}[/.-]\d{4})"],
        "sex": [r"SEX[:\s]*([MF])", r"GENDER[:\s]*(MALE|FEMALE)"],
        "nationality": [r"NATIONALITY[:\s]*([A-Z]+)"],
        "place_of_birth": [r"(?:DISTRICT|PLACE)\s*OF\s*BIRTH[:\s]*([A-Z\s]+)"],
        "date_of_issue": [r"DATE\s*OF\s*ISSUE[:\s]*([\d/.-]+)"],
        "date_of_expiry": [r"(?:DATE\s*OF\s*)?EXPIR[YE][:\s]*([\d/.-]+)"],
    }

    def extract(self, regions: list[TextRegion]) -> list[DocumentField]:
        full_text = " ".join(r.text for r in regions)
        fields = []

        for field_name, patterns in self.FIELD_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Find the region that contains this value
                    source = next((r for r in regions if value.upper() in r.text.upper()), None)
                    fields.append(DocumentField(
                        field_name=field_name,
                        value=value,
                        confidence=source.confidence if source else 0.8,
                        source_region=source,
                        validated=True,
                        validation_method="regex_pattern"
                    ))
                    break

        return fields


class PassportExtractor:
    """Extract structured fields from passports including MRZ."""

    MRZ_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"

    def extract_mrz(self, regions: list[TextRegion]) -> Optional[MRZData]:
        """Extract and parse Machine Readable Zone from passport.

        Returns None when no MRZ lines are detected — no fabricated
        passport data is ever returned.
        """
        mrz_lines = []
        for region in regions:
            text = region.text.replace(" ", "").upper()
            if len(text) >= 30 and all(c in self.MRZ_CHARS for c in text):
                mrz_lines.append(text)

        if len(mrz_lines) < 2:
            logger.info("No MRZ lines detected in OCR output; skipping MRZ parse")
            return None

        # Parse TD3 (passport) MRZ
        line1, line2 = mrz_lines[0], mrz_lines[1]
        if len(line1) < 44 or len(line2) < 44:
            logger.warning("MRZ lines shorter than TD3 length (44); cannot parse reliably")
            return None

        return MRZData(
            raw_lines=[line1, line2],
            document_type=line1[0],
            country_code=line1[2:5].replace("<", ""),
            surname=line1[5:].split("<<")[0].replace("<", " ").strip(),
            given_names=line1[5:].split("<<")[1].replace("<", " ").strip() if "<<" in line1[5:] else "",
            document_number=line2[0:9].replace("<", ""),
            nationality=line2[10:13].replace("<", ""),
            date_of_birth=line2[13:19],
            sex=line2[20],
            expiry_date=line2[21:27],
            personal_number=line2[28:42].replace("<", "").strip() or None,
            check_digits_valid=self._verify_check_digits(line2),
        )

    def _verify_check_digits(self, line2: str) -> bool:
        """Verify MRZ check digits using the ICAO 9303 algorithm (TD3).

        Checks, in order:
          1. Document number   — line2[0:9]   vs line2[9]
          2. Date of birth     — line2[13:19] vs line2[19]
          3. Expiry date       — line2[21:27] vs line2[27]
          4. Personal number   — line2[28:42] vs line2[42]
          5. Composite         — line2[0:10] + line2[13:20] + line2[21:43] vs line2[43]
        Weights cycle 7-3-1; '<' counts as 0; letters map A=10..Z=35.
        """
        if len(line2) < 44:
            return False

        weights = [7, 3, 1]

        def compute(data: str) -> int:
            total = 0
            for i, c in enumerate(data):
                if c == "<":
                    val = 0
                elif c.isdigit():
                    val = int(c)
                elif "A" <= c <= "Z":
                    val = ord(c) - ord("A") + 10
                else:
                    return -1  # invalid character -> fail check
                total += val * weights[i % 3]
            return total % 10

        def expected_digit(ch: str) -> Optional[int]:
            return int(ch) if ch.isdigit() else None

        checks = [
            (line2[0:9], expected_digit(line2[9])),                                     # document number
            (line2[13:19], expected_digit(line2[19])),                                  # date of birth
            (line2[21:27], expected_digit(line2[27])),                                  # expiry date
            (line2[28:42], expected_digit(line2[42])),                                  # personal number
            (line2[0:10] + line2[13:20] + line2[21:43], expected_digit(line2[43])),     # composite
        ]

        for data, expected in checks:
            if expected is None:
                return False
            if compute(data) != expected:
                return False
        return True


class UtilityBillExtractor:
    """Extract address and account holder info from utility bills."""

    def extract(self, regions: list[TextRegion]) -> list[DocumentField]:
        fields = []
        full_text = " ".join(r.text for r in regions)

        # Address extraction heuristics
        address_patterns = [
            r"(?:ADDRESS|PREMISES)[:\s]*([\w\s,.-]+(?:ROAD|STREET|AVENUE|DRIVE|LANE|WAY|BLVD)[\w\s,.-]*)",
            r"P\.?O\.?\s*BOX\s*\d+[\w\s,-]*",
        ]
        for pattern in address_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                fields.append(DocumentField(
                    field_name="address",
                    value=match.group(0).strip(),
                    confidence=0.85,
                    validated=True,
                    validation_method="address_pattern"
                ))
                break

        # Account holder name
        name_patterns = [r"(?:ACCOUNT\s*HOLDER|CUSTOMER\s*NAME|NAME)[:\s]*([A-Z\s]{3,40})"]
        for pattern in name_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                fields.append(DocumentField(
                    field_name="account_holder",
                    value=match.group(1).strip(),
                    confidence=0.82,
                    validated=True,
                    validation_method="name_pattern"
                ))
                break

        # Bill date
        date_match = re.search(r"(?:BILL\s*DATE|DATE)[:\s]*([\d/.-]+\d{4})", full_text, re.IGNORECASE)
        if date_match:
            fields.append(DocumentField(
                field_name="bill_date",
                value=date_match.group(1),
                confidence=0.90,
                validated=True,
                validation_method="date_pattern"
            ))

        return fields


class BusinessDocExtractor:
    """Extract business registration details."""

    def extract(self, regions: list[TextRegion]) -> list[DocumentField]:
        fields = []
        full_text = " ".join(r.text for r in regions)

        patterns = {
            "company_name": [r"(?:COMPANY|BUSINESS)\s*NAME[:\s]*([A-Z\s&.,]+(?:LTD|LLC|INC|PLC|CO))"],
            "registration_number": [r"(?:REG(?:ISTRATION)?\s*(?:NO|NUMBER)|CR\s*NO)[:\s]*([\w/-]+)"],
            "date_of_incorporation": [r"(?:DATE\s*OF\s*)?INCORPORAT(?:ION|ED)[:\s]*([\d/.-]+)"],
            "registered_address": [r"REGISTERED\s*(?:OFFICE|ADDRESS)[:\s]*([\w\s,.-]+)"],
            "directors": [r"DIRECTOR[S]?[:\s]*([\w\s,]+)"],
            "share_capital": [r"(?:SHARE|AUTHORIZED)\s*CAPITAL[:\s]*([\w\s,.]+)"],
        }

        for field_name, pats in patterns.items():
            for pat in pats:
                match = re.search(pat, full_text, re.IGNORECASE)
                if match:
                    fields.append(DocumentField(
                        field_name=field_name,
                        value=match.group(1).strip(),
                        confidence=0.85,
                        validated=True,
                        validation_method="business_pattern"
                    ))
                    break

        return fields


# ── Service Initialization ────────────────────────────────────────────────────

ocr_engine = PaddleOCREngine()
id_extractor = IDCardExtractor()
passport_extractor = PassportExtractor()
utility_extractor = UtilityBillExtractor()
business_extractor = BusinessDocExtractor()


# ── API Endpoints ─────────────────────────────────────────────────────────────

class OCRRequest(BaseModel):
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    document_type: Optional[DocumentType] = None
    language: str = "en"


@app.post("/ocr/extract")
async def extract_document(req: OCRRequest):
    """Full document OCR with auto-detection and structured output."""
    start = time.monotonic()
    request_id = str(uuid.uuid4())

    # Get image bytes
    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception as e:
            raise HTTPException(400, f"Invalid base64 image data: {e}")
    elif req.image_url:
        import urllib.request
        try:
            with urllib.request.urlopen(req.image_url, timeout=15) as resp:
                image_bytes = resp.read()
        except Exception as e:
            raise HTTPException(502, f"Failed to download image from URL: {e}")
    else:
        raise HTTPException(400, "Provide image_base64 or image_url")

    # Run OCR (raises 503 if the engine is unavailable — never returns fixtures)
    regions = await ocr_engine.extract_text(image_bytes, req.language)
    quality = ocr_engine.assess_image_quality(image_bytes)

    # Auto-detect document type if not specified
    doc_type = req.document_type or _detect_document_type(regions)

    # Extract fields based on document type
    fields = []
    mrz = None
    if doc_type == DocumentType.ID_CARD:
        fields = id_extractor.extract(regions)
    elif doc_type == DocumentType.PASSPORT:
        fields = id_extractor.extract(regions)
        mrz = passport_extractor.extract_mrz(regions)
    elif doc_type == DocumentType.UTILITY_BILL:
        fields = utility_extractor.extract(regions)
    elif doc_type in (DocumentType.BUSINESS_REGISTRATION, DocumentType.TAX_CERTIFICATE):
        fields = business_extractor.extract(regions)

    # Calculate overall confidence
    if regions:
        avg_conf = sum(r.confidence for r in regions) / len(regions)
    else:
        avg_conf = 0.0

    conf_level = OCRConfidence.HIGH if avg_conf > 0.95 else (
        OCRConfidence.MEDIUM if avg_conf > 0.80 else OCRConfidence.LOW
    )

    warnings = []
    if quality < 0.5:
        warnings.append("Low image quality — results may be inaccurate")
    if avg_conf < 0.80:
        warnings.append("Low OCR confidence — manual review recommended")
    if doc_type == DocumentType.PASSPORT and mrz is None:
        warnings.append("No MRZ detected — unable to verify passport machine-readable zone")
    if mrz is not None and not mrz.check_digits_valid:
        warnings.append("MRZ check digit verification failed (ICAO 9303) — possible forgery or OCR error")

    result = OCRResult(
        request_id=request_id,
        document_type=doc_type,
        language=req.language,
        text_regions=regions,
        extracted_fields=fields,
        mrz_data=mrz,
        full_text=" ".join(r.text for r in regions),
        confidence_overall=round(avg_conf, 4),
        confidence_level=conf_level,
        processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        image_quality_score=quality,
        warnings=warnings,
    )

    return asdict(result)


@app.post("/ocr/id-card")
async def extract_id_card(req: OCRRequest):
    req.document_type = DocumentType.ID_CARD
    return await extract_document(req)


@app.post("/ocr/passport")
async def extract_passport(req: OCRRequest):
    req.document_type = DocumentType.PASSPORT
    return await extract_document(req)


@app.post("/ocr/utility-bill")
async def extract_utility_bill(req: OCRRequest):
    req.document_type = DocumentType.UTILITY_BILL
    return await extract_document(req)


@app.post("/ocr/business-doc")
async def extract_business_doc(req: OCRRequest):
    req.document_type = DocumentType.BUSINESS_REGISTRATION
    return await extract_document(req)


@app.get("/health")
async def health():
    return {
        "status": "healthy" if ocr_engine.initialized else "degraded",
        "service": "paddle-ocr",
        "version": "2.0.0",
        "engine_initialized": ocr_engine.initialized,
        "engine_error": ocr_engine.init_error,
        "supported_languages": ["en", "fr", "sw", "ar", "zh", "hi", "pt", "es"],
        "supported_documents": [dt.value for dt in DocumentType],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_document_type(regions: list[TextRegion]) -> DocumentType:
    """Auto-detect document type from OCR text."""
    full_text = " ".join(r.text for r in regions).upper()

    if any(kw in full_text for kw in ["PASSPORT", "PASSEPORT", "TRAVEL DOCUMENT"]):
        return DocumentType.PASSPORT
    if any(kw in full_text for kw in ["IDENTITY CARD", "NATIONAL ID", "ID CARD", "CARTE D'IDENTITE"]):
        return DocumentType.ID_CARD
    if any(kw in full_text for kw in ["DRIVER", "LICENCE", "LICENSE"]):
        return DocumentType.DRIVERS_LICENSE
    if any(kw in full_text for kw in ["ELECTRICITY", "WATER", "GAS", "UTILITY", "BILL"]):
        return DocumentType.UTILITY_BILL
    if any(kw in full_text for kw in ["BANK STATEMENT", "ACCOUNT STATEMENT"]):
        return DocumentType.BANK_STATEMENT
    if any(kw in full_text for kw in ["CERTIFICATE OF INCORPORATION", "BUSINESS REGISTRATION", "COMPANY"]):
        return DocumentType.BUSINESS_REGISTRATION
    if any(kw in full_text for kw in ["TAX", "KRA", "TIN", "REVENUE"]):
        return DocumentType.TAX_CERTIFICATE

    return DocumentType.UNKNOWN


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port)
