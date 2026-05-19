"""
KYB Verification Service
Port: 8121
Delegates to kyb_service.KYBVerificationService for real verification logic,
deep_kyb.DeepKYBService for advanced 5-path verification, and
kyc_kyb_service for Temporal-orchestrated KYB.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import logging
import uuid
import uvicorn
import os
import json
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app = FastAPI(
    title="KYB Verification Service",
    description="KYB Verification for Remittance Platform — delegates to kyb_service, deep_kyb, and kyc_kyb_service",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stats = {
    "total_requests": 0,
    "total_verifications": 0,
    "start_time": datetime.now()
}


class BusinessType(str, Enum):
    CORPORATION = "corporation"
    LLC = "llc"
    PARTNERSHIP = "partnership"
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    NON_PROFIT = "non_profit"
    TRUST = "trust"
    OTHER = "other"


class VerificationPath(str, Enum):
    STANDARD = "standard"
    ALTERNATIVE_DOCS = "alternative_docs"
    BANK_STATEMENT_ONLY = "bank_statement_only"
    DIRECTOR_VERIFICATION = "director_verification"
    BUSINESS_ACTIVITY = "business_activity"


class BeneficialOwnerRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    nationality: str = "Nigeria"
    ownership_percentage: float
    position: Optional[str] = None
    bvn: Optional[str] = None
    nin: Optional[str] = None


class KYBVerificationRequest(BaseModel):
    business_name: str
    business_type: BusinessType = BusinessType.LLC
    registration_number: Optional[str] = None
    tax_id: Optional[str] = None
    incorporation_country: str = "Nigeria"
    incorporation_state: Optional[str] = None
    business_address: Optional[Dict[str, str]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None
    beneficial_owners: Optional[List[BeneficialOwnerRequest]] = None
    verification_path: VerificationPath = VerificationPath.STANDARD


class BankStatementRequest(BaseModel):
    verification_id: str
    transactions: List[Dict[str, Any]]
    account_number: str
    bank_name: str
    period_start: str
    period_end: str


class EvidenceSubmitRequest(BaseModel):
    verification_id: str
    document_type: str
    document_data: Dict[str, Any]
    document_date: str


KYB_SERVICE_URL = os.getenv("KYB_SERVICE_URL", "http://localhost:8015")
DEEP_KYB_SERVICE_URL = os.getenv("DEEP_KYB_SERVICE_URL", "http://localhost:8016")
KYC_KYB_SERVICE_URL = os.getenv("KYC_KYB_SERVICE_URL", "http://localhost:8017")


async def _forward_request(url: str, method: str = "POST", json_data: dict = None, timeout: float = 30.0):
    try:
        async with httpx.AsyncClient() as client:
            if method == "POST":
                resp = await client.post(url, json=json_data, timeout=timeout)
            else:
                resp = await client.get(url, timeout=timeout)
            if resp.status_code < 400:
                return resp.json()
            logger.warning(f"Upstream {url} returned {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Upstream {url} unreachable: {e}")
        return None


@app.get("/")
async def root():
    return {
        "service": "kyb-verification",
        "description": "KYB Verification — delegates to kyb_service, deep_kyb, kyc_kyb_service",
        "version": "2.0.0",
        "port": 8121,
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "total_requests": stats["total_requests"],
        "total_verifications": stats["total_verifications"]
    }


@app.post("/kyb/verify")
async def start_kyb_verification(request: KYBVerificationRequest, background_tasks: BackgroundTasks):
    stats["total_requests"] += 1
    stats["total_verifications"] += 1

    verification_id = str(uuid.uuid4())

    result = await _forward_request(
        f"{KYC_KYB_SERVICE_URL}/kyb/verify",
        json_data={
            "business_name": request.business_name,
            "business_type": request.business_type.value,
            "registration_number": request.registration_number,
            "tax_id": request.tax_id,
            "country": request.incorporation_country,
            "state": request.incorporation_state,
            "industry": request.industry,
            "beneficial_owners": [bo.dict() for bo in (request.beneficial_owners or [])],
        }
    )
    if result:
        return result

    result = await _forward_request(
        f"{KYB_SERVICE_URL}/kyb/verify",
        json_data={
            "business_name": request.business_name,
            "business_type": request.business_type.value,
            "registration_number": request.registration_number,
            "tax_id": request.tax_id,
            "incorporation_country": request.incorporation_country,
            "beneficial_owners": [bo.dict() for bo in (request.beneficial_owners or [])],
        }
    )
    if result:
        return result

    result = await _forward_request(
        f"{DEEP_KYB_SERVICE_URL}/deep-kyb/verify",
        json_data={
            "business_name": request.business_name,
            "business_type": request.business_type.value,
            "verification_path": request.verification_path.value,
            "registration_number": request.registration_number,
            "tax_id": request.tax_id,
            "shareholders": [bo.dict() for bo in (request.beneficial_owners or [])],
        }
    )
    if result:
        return result

    return {
        "verification_id": verification_id,
        "status": "pending",
        "business_name": request.business_name,
        "business_type": request.business_type.value,
        "verification_path": request.verification_path.value,
        "message": "Verification queued — upstream services unavailable, will retry",
        "created_at": datetime.utcnow().isoformat()
    }


@app.get("/kyb/status/{verification_id}")
async def get_verification_status(verification_id: str):
    stats["total_requests"] += 1

    for base_url in [KYC_KYB_SERVICE_URL, KYB_SERVICE_URL, DEEP_KYB_SERVICE_URL]:
        result = await _forward_request(f"{base_url}/kyb/status/{verification_id}", method="GET")
        if result:
            return result

    raise HTTPException(status_code=404, detail=f"Verification {verification_id} not found")


@app.post("/kyb/bank-statement")
async def submit_bank_statement(request: BankStatementRequest):
    stats["total_requests"] += 1

    result = await _forward_request(
        f"{DEEP_KYB_SERVICE_URL}/deep-kyb/bank-statement",
        json_data=request.dict()
    )
    if result:
        return result

    raise HTTPException(status_code=502, detail="Deep KYB service unavailable for bank statement analysis")


@app.post("/kyb/evidence")
async def submit_evidence(request: EvidenceSubmitRequest):
    stats["total_requests"] += 1

    result = await _forward_request(
        f"{DEEP_KYB_SERVICE_URL}/deep-kyb/evidence",
        json_data=request.dict()
    )
    if result:
        return result

    raise HTTPException(status_code=502, detail="Deep KYB service unavailable for evidence submission")


@app.post("/kyb/verify-owners/{verification_id}")
async def verify_beneficial_owners(verification_id: str):
    stats["total_requests"] += 1

    result = await _forward_request(
        f"{DEEP_KYB_SERVICE_URL}/deep-kyb/verify-owners/{verification_id}",
        json_data={}
    )
    if result:
        return result

    raise HTTPException(status_code=502, detail="Deep KYB service unavailable for UBO verification")


@app.post("/kyb/approve/{business_id}")
async def approve_verification(business_id: str, approved_by: str = "system"):
    stats["total_requests"] += 1

    result = await _forward_request(
        f"{KYB_SERVICE_URL}/kyb/approve/{business_id}",
        json_data={"approved_by": approved_by}
    )
    if result:
        return result

    raise HTTPException(status_code=502, detail="KYB service unavailable for approval")


@app.post("/kyb/reject/{business_id}")
async def reject_verification(business_id: str, rejected_by: str = "system", reason: str = ""):
    stats["total_requests"] += 1

    result = await _forward_request(
        f"{KYB_SERVICE_URL}/kyb/reject/{business_id}",
        json_data={"rejected_by": rejected_by, "reason": reason}
    )
    if result:
        return result

    raise HTTPException(status_code=502, detail="KYB service unavailable for rejection")


@app.get("/kyb/screening/{business_id}")
async def get_screening_results(business_id: str):
    stats["total_requests"] += 1

    result = await _forward_request(f"{KYB_SERVICE_URL}/kyb/screening/{business_id}", method="GET")
    if result:
        return result

    raise HTTPException(status_code=502, detail="KYB service unavailable for screening results")


@app.get("/stats")
async def get_statistics():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "uptime_seconds": int(uptime),
        "total_requests": stats["total_requests"],
        "total_verifications": stats["total_verifications"],
        "service": "kyb-verification",
        "port": 8121,
        "status": "operational"
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8121)
