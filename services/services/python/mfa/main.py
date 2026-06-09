"""
MFA Service - Multi-factor authentication
Supports TOTP, SMS OTP, and email OTP verification
Database-backed with rate limiting and audit logging
"""

from fastapi import FastAPI, HTTPException, Header, Depends
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from enum import Enum
import asyncpg
import uuid
import os
import logging
import secrets
import hashlib
import hmac
import struct
import time
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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mfa")
SMS_GATEWAY_URL = os.getenv("SMS_GATEWAY_URL", "")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", "http://localhost:8025")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MFA Service", version="2.0.0")
apply_middleware(app, enable_auth=True)

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/mfa")

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool: Optional[asyncpg.Pool] = None

class MFAMethod(str, Enum):
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"

class EnrollRequest(BaseModel):
    user_id: str
    method: MFAMethod
    phone_number: Optional[str] = None
    email: Optional[str] = None

class VerifyRequest(BaseModel):
    user_id: str
    code: str
    method: MFAMethod

async def verify_bearer_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    return token

def _generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8")

def _compute_totp(secret_b32: str, time_step: int = 30) -> str:
    key = base64.b32decode(secret_b32.upper())
    counter = int(time.time()) // time_step
    msg = struct.pack(">Q", counter)
    # RFC 6238 TOTP requires HMAC-SHA1 for compatibility with authenticator apps
    # RFC 6238 TOTP requires HMAC-SHA1 for compatibility with authenticator apps
    # RFC 6238 TOTP requires HMAC-SHA1 for compatibility with authenticator apps
    h = hmac.new(key, msg, hashlib.sha1).digest()  # noqa: S324 - RFC 6238 protocol requirement  # noqa: S324 - RFC 6238 protocol requirement  # noqa: S324 - RFC 6238 protocol requirement
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1000000).zfill(6)

def _generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mfa_enrollments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(100) NOT NULL,
                method VARCHAR(20) NOT NULL,
                secret VARCHAR(255),
                phone_number VARCHAR(20),
                email VARCHAR(255),
                is_verified BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, method)
            );
            CREATE TABLE IF NOT EXISTS mfa_challenges (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(100) NOT NULL,
                method VARCHAR(20) NOT NULL,
                code_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                attempts INT DEFAULT 0,
                verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS mfa_audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(100) NOT NULL,
                action VARCHAR(50) NOT NULL,
                method VARCHAR(20),
                success BOOLEAN,
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_mfa_enrollments_user ON mfa_enrollments(user_id);
            CREATE INDEX IF NOT EXISTS idx_mfa_challenges_user ON mfa_challenges(user_id, expires_at);
        """)
    logger.info("MFA Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/api/v1/mfa/enroll")
async def enroll_mfa(req: EnrollRequest, token: str = Depends(verify_bearer_token)):
    if req.method == MFAMethod.SMS and not req.phone_number:
        raise HTTPException(status_code=400, detail="Phone number required for SMS MFA")
    if req.method == MFAMethod.EMAIL and not req.email:
        raise HTTPException(status_code=400, detail="Email required for email MFA")

    secret = _generate_totp_secret() if req.method == MFAMethod.TOTP else None

    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO mfa_enrollments (user_id, method, secret, phone_number, email)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, method) DO UPDATE SET
                secret = EXCLUDED.secret, phone_number = EXCLUDED.phone_number,
                email = EXCLUDED.email, is_active = TRUE""",
            req.user_id, req.method.value, secret, req.phone_number, req.email,
        )

    result = {"user_id": req.user_id, "method": req.method.value, "enrolled": True}
    if req.method == MFAMethod.TOTP:
        result["totp_uri"] = f"otpauth://totp/RemittancePlatform:{req.user_id}?secret={secret}&issuer=RemittancePlatform"
        result["secret"] = secret
    logger.info(f"MFA enrolled: user={req.user_id} method={req.method.value}")
    return result

@app.post("/api/v1/mfa/challenge")
async def send_challenge(user_id: str, method: MFAMethod, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        enrollment = await conn.fetchrow(
            "SELECT * FROM mfa_enrollments WHERE user_id = $1 AND method = $2 AND is_active = TRUE",
            user_id, method.value,
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="MFA not enrolled for this method")

        active = await conn.fetchval(
            "SELECT COUNT(*) FROM mfa_challenges WHERE user_id = $1 AND created_at > NOW() - INTERVAL '1 minute'",
            user_id,
        )
        if active >= 3:
            raise HTTPException(status_code=429, detail="Too many challenges. Wait 1 minute.")

    if method == MFAMethod.TOTP:
        return {"user_id": user_id, "method": "totp", "message": "Use your authenticator app"}

    otp = _generate_otp()
    code_hash = hashlib.sha256(otp.encode()).hexdigest()

    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO mfa_challenges (user_id, method, code_hash, expires_at)
            VALUES ($1, $2, $3, NOW() + INTERVAL '5 minutes')""",
            user_id, method.value, code_hash,
        )

    if method == MFAMethod.SMS and SMS_GATEWAY_URL and enrollment["phone_number"]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(SMS_GATEWAY_URL, json={
                    "to": enrollment["phone_number"],
                    "message": f"Your verification code is: {otp}",
                }, headers={"Authorization": f"Bearer {SMS_API_KEY}"})
        except Exception as e:
            logger.error(f"SMS send failed: {e}")

    if method == MFAMethod.EMAIL and enrollment["email"]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{EMAIL_SERVICE_URL}/api/v1/send", json={
                    "to": enrollment["email"],
                    "subject": "Your verification code",
                    "body": f"Your verification code is: {otp}. It expires in 5 minutes.",
                })
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    return {"user_id": user_id, "method": method.value, "message": "Verification code sent"}

@app.post("/api/v1/mfa/verify")
async def verify_mfa(req: VerifyRequest, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        enrollment = await conn.fetchrow(
            "SELECT * FROM mfa_enrollments WHERE user_id = $1 AND method = $2 AND is_active = TRUE",
            req.user_id, req.method.value,
        )
        if not enrollment:
            raise HTTPException(status_code=404, detail="MFA not enrolled")

        if req.method == MFAMethod.TOTP:
            expected = _compute_totp(enrollment["secret"])
            valid = hmac.compare_digest(req.code, expected)
        else:
            code_hash = hashlib.sha256(req.code.encode()).hexdigest()
            challenge = await conn.fetchrow(
                """SELECT * FROM mfa_challenges
                WHERE user_id = $1 AND method = $2 AND code_hash = $3
                AND expires_at > NOW() AND verified = FALSE AND attempts < 5
                ORDER BY created_at DESC LIMIT 1""",
                req.user_id, req.method.value, code_hash,
            )
            valid = challenge is not None
            if challenge:
                await conn.execute(
                    "UPDATE mfa_challenges SET verified = TRUE WHERE id = $1",
                    challenge["id"],
                )
            else:
                await conn.execute(
                    """UPDATE mfa_challenges SET attempts = attempts + 1
                    WHERE user_id = $1 AND method = $2 AND expires_at > NOW() AND verified = FALSE""",
                    req.user_id, req.method.value,
                )

        if not enrollment["is_verified"] and valid:
            await conn.execute(
                "UPDATE mfa_enrollments SET is_verified = TRUE WHERE user_id = $1 AND method = $2",
                req.user_id, req.method.value,
            )

        await conn.execute(
            "INSERT INTO mfa_audit_log (user_id, action, method, success) VALUES ($1, 'verify', $2, $3)",
            req.user_id, req.method.value, valid,
        )

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid verification code")
    logger.info(f"MFA verified: user={req.user_id} method={req.method.value}")
    return {"user_id": req.user_id, "verified": True, "method": req.method.value}

@app.get("/api/v1/mfa/status/{user_id}")
async def get_mfa_status(user_id: str, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT method, is_verified, is_active, created_at FROM mfa_enrollments WHERE user_id = $1",
            user_id,
        )
    methods = [
        {"method": r["method"], "verified": r["is_verified"], "active": r["is_active"], "enrolled_at": r["created_at"].isoformat()}
        for r in rows
    ]
    return {"user_id": user_id, "mfa_enabled": any(r["is_verified"] and r["is_active"] for r in rows), "methods": methods}

@app.delete("/api/v1/mfa/unenroll")
async def unenroll_mfa(user_id: str, method: MFAMethod, token: str = Depends(verify_bearer_token)):
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE mfa_enrollments SET is_active = FALSE WHERE user_id = $1 AND method = $2",
            user_id, method.value,
        )
        await conn.execute(
            "INSERT INTO mfa_audit_log (user_id, action, method, success) VALUES ($1, 'unenroll', $2, TRUE)",
            user_id, method.value,
        )
    return {"user_id": user_id, "method": method.value, "unenrolled": True}

@app.get("/health")
async def health_check():
    db_ok = False
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass
    return {"status": "healthy" if db_ok else "degraded", "service": "mfa-service", "database": db_ok}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)

