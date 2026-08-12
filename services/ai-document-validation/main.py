"""
AI Document Validation Service
AI-powered document verification for KYC

Features:
- ID card verification (National ID, Driver's License, Passport)
- Face matching
- Document authenticity check
- OCR text extraction
- Liveness detection

FAIL-CLOSED POLICY: documents are only marked VERIFIED after a real AI
validation provider responds positively. When no provider is configured
or the provider fails, the validation is persisted as UNVERIFIABLE and
the API fails loudly with HTTP 503. This service NEVER fabricates
extracted identity data or a VERIFIED status.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import asyncpg
import os
import logging
import base64
import httpx

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/documents")

# External AI validation provider (e.g. AWS Rekognition / Azure Computer
# Vision / Google Cloud Vision gateway). Validation is IMPOSSIBLE without
# a configured provider - the service fails closed in that case.
AI_VALIDATION_PROVIDER_URL = os.getenv("AI_VALIDATION_PROVIDER_URL", "")
AI_VALIDATION_API_KEY = os.getenv("AI_VALIDATION_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Document Validation Service", version="1.0.0")
db_pool = None

class DocumentType(str, Enum):
    NATIONAL_ID = "national_id"
    DRIVERS_LICENSE = "drivers_license"
    PASSPORT = "passport"
    UTILITY_BILL = "utility_bill"

class ValidationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNVERIFIABLE = "unverifiable"

class ValidationResult(BaseModel):
    id: str
    document_type: DocumentType
    status: ValidationStatus
    confidence_score: float
    extracted_data: Dict[str, Any]
    created_at: datetime


class DocumentValidationUnavailable(Exception):
    """Raised when no real AI validation can be performed (provider not
    configured, unreachable, or erroring)."""
    pass

@app.on_event("startup")
async def startup():
    global db_pool
    if not AI_VALIDATION_PROVIDER_URL:
        logger.error(
            "AI_VALIDATION_PROVIDER_URL is not configured - document validation "
            "will fail closed (UNVERIFIABLE / HTTP 503) until a real AI provider is set"
        )
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_validations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR(100) NOT NULL,
                    document_type VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    confidence_score DECIMAL(5,2),
                    extracted_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
        logger.info("AI Document Validation Service started")
    except Exception as e:
        logger.error(f"DB init failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def validate_document_ai(file_content: bytes, doc_type: DocumentType) -> tuple[bool, float, Dict]:
    """Validate a document with the configured external AI provider.

    Raises DocumentValidationUnavailable when no real validation can be
    performed. NEVER returns simulated confidence or fabricated identity
    data.
    """
    if not AI_VALIDATION_PROVIDER_URL:
        raise DocumentValidationUnavailable(
            "No AI validation provider configured (AI_VALIDATION_PROVIDER_URL unset)"
        )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                AI_VALIDATION_PROVIDER_URL,
                headers={
                    "Authorization": f"Bearer {AI_VALIDATION_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "document_type": doc_type.value,
                    "image_base64": base64.b64encode(file_content).decode("ascii"),
                },
            )
    except Exception as e:
        raise DocumentValidationUnavailable(f"AI validation provider unreachable: {e}") from e

    if response.status_code != 200:
        raise DocumentValidationUnavailable(
            f"AI validation provider returned status {response.status_code}"
        )

    try:
        payload = response.json()
    except Exception as e:
        raise DocumentValidationUnavailable(
            f"AI validation provider returned an unparseable response: {e}"
        ) from e

    is_valid = bool(payload.get("is_valid"))
    confidence = float(payload.get("confidence", 0.0))
    extracted_data = payload.get("extracted_data") or {}
    return is_valid, confidence, extracted_data

@app.post("/validate", response_model=ValidationResult)
async def validate_document(
    user_id: str,
    document_type: DocumentType,
    file: UploadFile = File(...)
):
    """Validate uploaded document.

    Fail-closed: if real AI validation cannot be performed, the attempt is
    persisted as UNVERIFIABLE (audit trail) and the request fails loudly
    with HTTP 503. A document is NEVER persisted as VERIFIED without a
    positive response from a real provider.
    """
    if db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Validation database is unavailable; cannot persist validation audit record"
        )

    file_content = await file.read()

    # Perform AI validation
    try:
        is_valid, confidence, extracted_data = await validate_document_ai(file_content, document_type)
    except DocumentValidationUnavailable as e:
        logger.error(
            f"AI document validation unavailable for user {user_id}: {e}. "
            "Persisting UNVERIFIABLE audit record."
        )
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO document_validations (user_id, document_type, status, confidence_score, extracted_data)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, document_type.value, ValidationStatus.UNVERIFIABLE.value, 0.0, {})
        raise HTTPException(
            status_code=503,
            detail=f"AI document validation is unavailable: {e}. "
                   "The document was recorded as UNVERIFIABLE and requires manual review."
        )

    status = ValidationStatus.VERIFIED if is_valid else ValidationStatus.REJECTED

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO document_validations (user_id, document_type, status, confidence_score, extracted_data)
            VALUES ($1, $2, $3, $4, $5) RETURNING *
        """, user_id, document_type.value, status.value, confidence, extracted_data)
        
        return ValidationResult(**dict(row))

@app.get("/validations/{validation_id}", response_model=ValidationResult)
async def get_validation(validation_id: str):
    """Get validation result"""
    if db_pool is None:
        raise HTTPException(status_code=503, detail="Validation database is unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM document_validations WHERE id = $1", validation_id)
        if not row:
            raise HTTPException(status_code=404, detail="Validation not found")
        return ValidationResult(**dict(row))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-document-validation",
        "ai_provider_configured": bool(AI_VALIDATION_PROVIDER_URL),
    }

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8107)
