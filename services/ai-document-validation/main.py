"""
AI Document Validation Service
AI-powered document verification for KYC

Features:
- ID card verification (National ID, Driver's License, Passport)
- Face matching
- Document authenticity check
- OCR text extraction
- Liveness detection
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import asyncpg
import httpx
import os
import logging
import base64

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
# Real AI document validation provider (e.g., an internal vision/IDV service).
# When unset, the service refuses to validate rather than simulating a result.
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

@app.on_event("startup")
async def startup():
    global db_pool
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
        logger.warning(f"DB init failed (non-fatal): {e}")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def validate_document_ai(file_content: bytes, doc_type: DocumentType) -> tuple[bool, float, Dict]:
    """Validate a document via the configured AI validation provider.

    Raises RuntimeError when no provider is configured or the provider call
    fails. This function MUST NOT fabricate validation results, extracted
    identities, or confidence scores.
    """
    if not AI_VALIDATION_PROVIDER_URL:
        raise RuntimeError(
            "AI document validation provider is not configured "
            "(AI_VALIDATION_PROVIDER_URL missing); document is unverifiable"
        )

    headers = {}
    if AI_VALIDATION_API_KEY:
        headers["Authorization"] = f"Bearer {AI_VALIDATION_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{AI_VALIDATION_PROVIDER_URL.rstrip('/')}/validate",
                files={"file": ("document", file_content)},
                data={"document_type": doc_type.value},
                headers=headers,
            )
    except httpx.HTTPError as e:
        raise RuntimeError(f"AI validation provider request failed: {e}") from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"AI validation provider error: HTTP {resp.status_code}"
        )

    result = resp.json()
    is_valid = bool(result.get("is_valid"))
    confidence = float(result.get("confidence", 0.0))
    extracted_data = result.get("extracted_data") or {}
    return is_valid, confidence, extracted_data

@app.post("/validate", response_model=ValidationResult)
async def validate_document(
    user_id: str,
    document_type: DocumentType,
    file: UploadFile = File(...)
):
    """Validate uploaded document.

    Fails closed: if the AI provider is not configured or fails, no verdict
    is persisted and the caller gets an explicit 503 (unverifiable).
    """
    
    file_content = await file.read()
    
    # Perform AI validation (real provider only)
    try:
        is_valid, confidence, extracted_data = await validate_document_ai(file_content, document_type)
    except RuntimeError as e:
        logger.error(f"Document validation unavailable for user {user_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Document validation unavailable: {e}. "
                   "Document status is unverifiable; manual review required."
        )
    
    status = ValidationStatus.VERIFIED if is_valid else ValidationStatus.REJECTED
    
    if db_pool is None:
        # Never return a verdict that was not persisted.
        raise HTTPException(status_code=503, detail="Validation store unavailable")
    
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
        raise HTTPException(status_code=503, detail="Validation store unavailable")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM document_validations WHERE id = $1", validation_id)
        if not row:
            raise HTTPException(status_code=404, detail="Validation not found")
        return ValidationResult(**dict(row))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-document-validation"}

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8107)
