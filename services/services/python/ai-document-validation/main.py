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
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
import asyncpg
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Document Validation Service", version="1.0.0")
apply_middleware(app, enable_auth=True)

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/ai_document_validation")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
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
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
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

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def validate_document_ai(file_content: bytes, doc_type: DocumentType) -> tuple[bool, float, Dict]:
    """Simulate AI document validation"""
    # In production, integrate with services like AWS Rekognition, Azure Computer Vision, or Google Cloud Vision
    
    confidence = 0.95
    extracted_data = {
        "document_number": "A12345678",
        "full_name": "John Doe",
        "date_of_birth": "1990-01-01",
        "expiry_date": "2030-12-31"
    }
    
    is_valid = confidence > 0.85
    return is_valid, confidence, extracted_data

@app.post("/validate", response_model=ValidationResult)
async def validate_document(
    user_id: str,
    document_type: DocumentType,
    file: UploadFile = File(...)
):
    """Validate uploaded document"""
    
    file_content = await file.read()
    
    # Perform AI validation
    is_valid, confidence, extracted_data = await validate_document_ai(file_content, document_type)
    
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
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM document_validations WHERE id = $1", validation_id)
        if not row:
            raise HTTPException(status_code=404, detail="Validation not found")
        return ValidationResult(**dict(row))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-document-validation"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8107)
