"""
Post-Quantum Cryptography API Service
RESTful API for quantum-resistant cryptographic operations
"""

from fastapi import FastAPI, HTTPException, Depends, Header
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

from pqc_service import PQCService

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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- PostgreSQL Persistence ---
import asyncpg
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/quantum_crypto")
_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def close_db_pool():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None

app = FastAPI(
    title="Post-Quantum Cryptography Service",
    description="Quantum-resistant cryptographic operations using NIST-standardized algorithms",
    version="1.0.0"
)
apply_middleware(app, enable_auth=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PQC service
pqc_service = PQCService()

# Request/Response Models
class KeyGenerationResponse(BaseModel):
    algorithm: str
    public_key: str
    secret_key: str
    created_at: str

class EncapsulateRequest(BaseModel):
    public_key: str

class EncapsulateResponse(BaseModel):
    ciphertext: str
    shared_secret: str
    algorithm: str

class DecapsulateRequest(BaseModel):
    secret_key: str
    ciphertext: str

class DecapsulateResponse(BaseModel):
    shared_secret: str
    algorithm: str

class SignRequest(BaseModel):
    secret_key: str
    message: str

class SignResponse(BaseModel):
    signature: str
    algorithm: str
    message_hash: str

class VerifyRequest(BaseModel):
    public_key: str
    message: str
    signature: str

class VerifyResponse(BaseModel):
    valid: bool
    algorithm: str
    verified_at: str

# API Key validation
async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key for authentication"""
    if x_api_key != "your-pqc-api-key":  # Replace with actual validation
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Post-Quantum Cryptography",
        "status": "operational",
        "algorithms": ["Kyber768", "Dilithium3"],
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "algorithms": {
            "kem": "Kyber768 (NIST Level 3)",
            "dsa": "Dilithium3 (NIST Level 3)"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/v1/kem/keypair", response_model=KeyGenerationResponse)
async def generate_kem_keypair(api_key: str = Depends(verify_api_key)):
    """Generate a Kyber768 keypair for key encapsulation"""
    try:
        result = pqc_service.create_secure_channel_keys()
        logger.info("Generated KEM keypair")
        return KeyGenerationResponse(**result)
    except Exception as e:
        logger.error(f"Error generating KEM keypair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/kem/encapsulate", response_model=EncapsulateResponse)
async def encapsulate_secret(
    request: EncapsulateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Encapsulate a shared secret using Kyber768"""
    try:
        result = pqc_service.establish_shared_secret(request.public_key)
        logger.info("Encapsulated shared secret")
        return EncapsulateResponse(**result)
    except Exception as e:
        logger.error(f"Error encapsulating secret: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/kem/decapsulate", response_model=DecapsulateResponse)
async def decapsulate_secret(
    request: DecapsulateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Decapsulate a shared secret using Kyber768"""
    try:
        result = pqc_service.derive_shared_secret(
            request.secret_key,
            request.ciphertext
        )
        logger.info("Decapsulated shared secret")
        return DecapsulateResponse(**result)
    except Exception as e:
        logger.error(f"Error decapsulating secret: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/dsa/keypair", response_model=KeyGenerationResponse)
async def generate_dsa_keypair(api_key: str = Depends(verify_api_key)):
    """Generate a Dilithium3 keypair for digital signatures"""
    try:
        result = pqc_service.create_signing_keys()
        logger.info("Generated DSA keypair")
        return KeyGenerationResponse(**result)
    except Exception as e:
        logger.error(f"Error generating DSA keypair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/dsa/sign", response_model=SignResponse)
async def sign_message(
    request: SignRequest,
    api_key: str = Depends(verify_api_key)
):
    """Sign a message using Dilithium3"""
    try:
        result = pqc_service.sign_message(request.secret_key, request.message)
        logger.info(f"Signed message: {request.message[:50]}...")
        return SignResponse(**result)
    except Exception as e:
        logger.error(f"Error signing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/dsa/verify", response_model=VerifyResponse)
async def verify_signature(
    request: VerifyRequest,
    api_key: str = Depends(verify_api_key)
):
    """Verify a signature using Dilithium3"""
    try:
        result = pqc_service.verify_signature(
            request.public_key,
            request.message,
            request.signature
        )
        logger.info(f"Verified signature: {result['valid']}")
        return VerifyResponse(**result)
    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def _startup():
    await get_db_pool()

@app.on_event("shutdown")
async def _shutdown():
    await close_db_pool()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
